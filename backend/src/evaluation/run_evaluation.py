#!/usr/bin/env python3
# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Principal-Grade CLI script for running brand evaluation against a golden dataset.
Handles workspace lifecycle, branding synchronization, parallel generation, and GCS archival.
"""

import argparse
import json
import logging
import sys
import time
import httpx
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional, Any
from concurrent.futures import ThreadPoolExecutor

from google.cloud import storage
from src.evaluation.brand_evaluator import BrandEvaluator, ValidationResult, TestCase
from src.config.config_service import config_service

# --- CONFIGURATION & CONSTANTS ---
DEFAULT_BACKEND_URL = "http://localhost:8080"
DEFAULT_EVAL_MODEL = "gemini-3-pro-preview"
DEFAULT_GEN_MODEL = "imagen-3.0-capability-001"
DEFAULT_MAX_WORKERS = 5
DEFAULT_POLL_RETRIES = 60
DEFAULT_POLL_DELAY = 5
AUTH_TOKEN = "dummy"  # Local bypass token

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("EvaluationRunner")


@dataclass
class EvaluationConfig:
    """Holds all configuration parameters for the evaluation run."""
    dataset_path: Path
    images_dir: Path
    workspace_id: int
    threshold: float
    output_path: Optional[Path]
    eval_model: str
    gen_model: str
    guideline_pdf: Optional[Path]
    max_workers: int
    backend_url: str = DEFAULT_BACKEND_URL


class GcsManager:
    """Helper for Google Cloud Storage operations."""
    
    def __init__(self, bucket_name: str):
        self.client = storage.Client()
        self.bucket = self.client.bucket(bucket_name)

    def upload_file(self, local_path: Path, gcs_uri: str) -> bool:
        """Uploads a local file to a GCS URI (gs://bucket/path)."""
        try:
            blob_name = gcs_uri.replace(f"gs://{self.bucket.name}/", "")
            blob = self.bucket.blob(blob_name)
            blob.upload_from_filename(str(local_path))
            logger.info(f"Uploaded: {local_path.name} -> {gcs_uri}")
            return True
        except Exception as e:
            logger.error(f"Failed GCS upload ({gcs_uri}): {e}")
            return False

    def download_file(self, gcs_uri: str, local_path: Path) -> bool:
        """Downloads a file from GCS to a local path."""
        try:
            blob_name = gcs_uri.replace(f"gs://{self.bucket.name}/", "")
            blob = self.bucket.blob(blob_name)
            blob.download_to_filename(str(local_path))
            return True
        except Exception as e:
            logger.error(f"Failed GCS download ({gcs_uri}): {e}")
            return False


class EvaluationClient:
    """Handles communication with the GCC Creative Studio Backend API."""

    def __init__(self, base_url: str, token: str):
        self.base_url = base_url
        self.token = token
        self.client = httpx.Client(timeout=30.0)

    def _get_url(self, path: str) -> str:
        sep = "&" if "?" in path else "?"
        return f"{self.base_url}{path}{sep}token={self.token}"

    def ensure_workspace(self, workspace_id: int) -> int:
        """Checks if a workspace exists, creates one if not."""
        response = self.client.get(self._get_url("/api/workspaces"))
        response.raise_for_status()
        workspaces = response.json()
        
        target = next((ws for ws in workspaces if ws["id"] == workspace_id), None)
        if target:
            logger.info(f"Using workspace {workspace_id}")
            return workspace_id

        logger.info(f"Workspace {workspace_id} not found. Creating dynamic evaluation workspace...")
        payload = {
            "name": f"Eval Workspace {uuid.uuid4().hex[:6]}",
            "description": "Generated for branding evaluation pipeline"
        }
        res = self.client.post(self._get_url("/api/workspaces"), json=payload)
        res.raise_for_status()
        new_id = res.json()["id"]
        logger.info(f"CREATED NEW WORKSPACE: {new_id}")
        return new_id

    def setup_branding(self, workspace_id: int, pdf_path: Path, gcs_uri: str) -> bool:
        """Finalizes PDF upload and polls for processing completion."""
        # 0. Check for existing completed guideline
        try:
            check_res = self.client.get(self._get_url(f"/api/brand-guidelines/workspace/{workspace_id}"))
            if check_res.status_code == 200:
                guideline = check_res.json()
                if guideline.get("status") == "completed":
                    logger.info(f"Workspace {workspace_id} already has a completed brand guideline. Skipping setup.")
                    return True
        except Exception:
            pass # Not found or error, proceed with setup

        # 1. Finalize

        # Poll
        logger.info(f"Polling for guideline processing (Workspace {workspace_id})...")
        for i in range(120):
            status_res = self.client.get(self._get_url(f"/api/brand-guidelines/workspace/{workspace_id}"))
            status_res.raise_for_status()
            guideline = status_res.json()
            
            status = guideline.get("status")
            if status == "completed":
                logger.info("✅ Branding processing finished.")
                return True
            if status == "failed":
                raise RuntimeError(f"Guideline processing failed: {guideline.get('errorMessage')}")
            
            if (i + 1) % 6 == 0:
                logger.info(f"  ...still processing ({i+1}/120)")
            time.sleep(10)
        
        return False

    def generate_image(self, test_id: str, prompt: str, workspace_id: int, model_id: str, refs: list[str]) -> dict:
        """Triggers image generation and returns the media item ID."""
        payload = {
            "prompt": prompt,
            "use_brand_guidelines": True,
            "workspace_id": workspace_id,
            "generation_model": model_id,
            "aspect_ratio": "1:1",
            "reference_image_gcs_uris": refs if refs else None
        }
        res = self.client.post(self._get_url("/api/images/generate-images"), json=payload)
        res.raise_for_status()
        return res.json()

    def poll_generation(self, media_id: int) -> dict:
        """Polls for generation completion."""
        for i in range(DEFAULT_POLL_RETRIES):
            res = self.client.get(self._get_url(f"/api/gallery/item/{media_id}"))
            res.raise_for_status()
            item = res.json()
            
            if item.get("status") in ["completed", "failed"]:
                return item
            
            time.sleep(DEFAULT_POLL_DELAY)
        
        return {"status": "timeout"}


class EvaluationRunner:
    """Orchestrates the evaluation lifecycle."""

    def __init__(self, config: EvaluationConfig):
        self.config = config
        self.run_id = str(uuid.uuid4())
        self.gcs_base = f"gs://{config_service.GENMEDIA_BUCKET}/evaluations/{self.run_id}"
        self.gcs = GcsManager(config_service.GENMEDIA_BUCKET)
        self.api = EvaluationClient(config.backend_url, AUTH_TOKEN)
        self.evaluator = BrandEvaluator(model_id=config.eval_model)

    def prepare_environment(self) -> int:
        """Initializes workspace and branding guidelines."""
        logger.info(f"Run ID: {self.run_id}")
        logger.info(f"GCS Base: {self.gcs_base}")
        
        workspace_id = self.api.ensure_workspace(self.config.workspace_id)
        
        if self.config.guideline_pdf:
            # 1. Archive PDF for the Judge (LLM-as-a-Judge)
            self.gcs.upload_file(self.config.guideline_pdf, f"{self.gcs_base}/guidelines.pdf")
            
            # 2. Setup branding if needed
            # Check for existing completed guideline first
            is_branded = False
            try:
                check_res = self.api.client.get(self.api._get_url(f"/api/brand-guidelines/workspace/{workspace_id}"))
                if check_res.status_code == 200:
                    guideline = check_res.json()
                    if guideline.get("status") == "completed":
                        logger.info(f"Workspace {workspace_id} already has a completed brand guideline. Skipping backend setup.")
                        is_branded = True
            except Exception:
                pass

            if not is_branded:
                # Backend Needs PDF in GCS for processing
                upload_uri = f"gs://{config_service.GENMEDIA_BUCKET}/brand-guidelines/{workspace_id}/uploads/{uuid.uuid4()}/{self.config.guideline_pdf.name}"
                self.gcs.upload_file(self.config.guideline_pdf, upload_uri)
                self.api.setup_branding(workspace_id, self.config.guideline_pdf, upload_uri)
            
        return workspace_id

    def run_test_case(self, test_case: TestCase, workspace_id: int) -> dict:
        """Executes a single test case end-to-end."""
        try:
            # 1. Upload Refs
            ref_uris = []
            for i, p in enumerate(test_case.reference_image_paths):
                path = Path(p)
                if path.exists():
                    uri = f"{self.gcs_base}/{test_case.id}/references/ref_{i}{path.suffix}"
                    if self.gcs.upload_file(path, uri):
                        ref_uris.append(uri)

            # 2. Generate
            media = self.api.generate_image(test_case.id, test_case.original_prompt, workspace_id, self.config.gen_model, ref_uris)
            result_item = self.api.poll_generation(media["id"])
            
            if result_item["status"] != "completed":
                return self._fail_result(test_case, f"Generation failed: {result_item.get('errorMessage')}")

            # 3. Download & Archive
            local_img = self.config.images_dir / f"{test_case.id}.png"
            # Try presigned first
            downloaded = False
            if result_item.get("presignedUrls"):
                try:
                    img_res = httpx.get(result_item["presignedUrls"][0])
                    img_res.raise_for_status()
                    local_img.write_bytes(img_res.content)
                    downloaded = True
                except: pass
            
            if not downloaded and result_item.get("gcsUris"):
                downloaded = self.gcs.download_file(result_item["gcsUris"][0], local_img)

            if not downloaded:
                return self._fail_result(test_case, "Failed to download generated image")

            self.gcs.upload_file(local_img, f"{self.gcs_base}/{test_case.id}/generated.png")

            # 4. Judge
            judge_pdf = f"{self.gcs_base}/guidelines.pdf" if self.config.guideline_pdf else None
            validation = self.evaluator.evaluate_image(test_case, str(local_img), guideline_pdf_path=judge_pdf)
            
            res = asdict(validation)
            res["generated_image_gcs_uri"] = f"{self.gcs_base}/{test_case.id}/generated.png"
            res["reference_image_gcs_uris"] = ref_uris
            return res

        except Exception as e:
            logger.error(f"Test {test_case.id} failed: {e}")
            return self._fail_result(test_case, str(e))

    def _fail_result(self, test_case: TestCase, reason: str) -> dict:
        return asdict(ValidationResult(
            test_id=test_case.id,
            image_path="N/A",
            is_compliant=False,
            score=0,
            reasoning=reason,
            issues=[reason],
            expected_compliant=test_case.expected_compliant
        ))

    def execute(self):
        """Runs the entire evaluation suite."""
        workspace_id = self.prepare_environment()
        
        self.config.images_dir.mkdir(exist_ok=True, parents=True)
        dataset = self.evaluator.load_golden_dataset(str(self.config.dataset_path))
        logger.info(f"Starting parallel evaluation ({len(dataset.test_cases)} cases, {self.config.max_workers} workers)...")

        with ThreadPoolExecutor(max_workers=self.config.max_workers) as executor:
            futures = [executor.submit(self.run_test_case, tc, workspace_id) for tc in dataset.test_cases]
            results = [f.result() for f in futures]

        self._report(results)

    def _report(self, results: list[dict]):
        """Computes metrics and saves/archives results."""
        total = len(results)
        passed = sum(1 for r in results if r["passed"])
        avg_score = sum(r["score"] for r in results) / total if total > 0 else 0
        rate = (passed / total * 100) if total > 0 else 0

        summary = {
            "run_id": self.run_id,
            "total_tests": total,
            "passed_tests": passed,
            "pass_rate": rate,
            "average_score": avg_score,
            "threshold": self.config.threshold,
            "gcs_base": self.gcs_base
        }

        print("\n" + "="*40 + "\nEVALUATION COMPLETE\n" + "="*40)
        print(json.dumps(summary, indent=2))
        
        full_output = {"summary": summary, "results": results}
        
        # Save & Archive
        tmp_json = Path("/tmp/eval_results.json")
        tmp_json.write_text(json.dumps(full_output, indent=2))
        self.gcs.upload_file(tmp_json, f"{self.gcs_base}/results.json")
        
        if self.config.output_path:
            self.config.output_path.write_text(json.dumps(full_output, indent=2))
            logger.info(f"Local results saved to: {self.config.output_path}")

        if rate < self.config.threshold:
            print(f"\n✗ FAILED: Pass rate {rate:.1f}% below threshold {self.config.threshold}%")
            sys.exit(1)
        else:
            print(f"\n✓ PASSED: Pass rate {rate:.1f}% meets threshold")
            sys.exit(0)


def main():
    parser = argparse.ArgumentParser(description="GCC Creative Studio Evaluation Pipeline")
    parser.add_argument("--dataset", type=str, required=True, help="Golden dataset JSON")
    parser.add_argument("--workspace-id", type=int, default=1, help="Target workspace")
    parser.add_argument("--threshold", type=float, default=80.0, help="Pass rate threshold")
    parser.add_argument("--output", type=str, help="Save JSON results locally")
    parser.add_argument("--eval-model", type=str, default=DEFAULT_EVAL_MODEL)
    parser.add_argument("--gen-model", type=str, default=DEFAULT_GEN_MODEL)
    parser.add_argument("--guideline-pdf", type=str, help="Brand guideline PDF")
    parser.add_argument("--max-workers", type=int, default=DEFAULT_MAX_WORKERS)
    parser.add_argument("--images-dir", type=str, default="generated_images")
    args = parser.parse_args()

    config = EvaluationConfig(
        dataset_path=Path(args.dataset),
        images_dir=Path(args.images_dir),
        workspace_id=args.workspace_id,
        threshold=args.threshold,
        output_path=Path(args.output) if args.output else None,
        eval_model=args.eval_model,
        gen_model=args.gen_model,
        guideline_pdf=Path(args.guideline_pdf) if args.guideline_pdf else None,
        max_workers=args.max_workers
    )

    runner = EvaluationRunner(config)
    try:
        runner.execute()
    except Exception as e:
        logger.error(f"Critical evaluation failure: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()