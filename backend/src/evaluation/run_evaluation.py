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
CLI script for running brand evaluation against a golden dataset.
This script now generates images using Imagen 3 before evaluating them.

Usage:
    python -m src.evaluation.run_evaluation --dataset path/to/golden_dataset.json
    
    # With custom threshold (default: 80)
    python -m src.evaluation.run_evaluation --dataset golden_dataset.json --threshold 90
    
    # Save results to file
    python -m src.evaluation.run_evaluation --dataset golden_dataset.json --output results.json

Exit Codes:
    0 - All tests passed (or met threshold)
    1 - One or more tests failed
"""

import argparse
import json
import logging
import sys
import base64
import os
from dataclasses import asdict
from pathlib import Path
from typing import Optional

from google.genai import Client, types
from src.evaluation.brand_evaluator import BrandEvaluator, ValidationResult, TestCase, EvaluationReport
from src.multimodal.schema.gemini_model_setup import GeminiModelSetup

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def generate_image_for_test_case(
    client: Client, 
    test_case: TestCase, 
    output_dir: Path,
    model_id: str = "imagen-3.0-generate-001"
) -> Optional[Path]:
    """
    Generates an image for a test case using the specified model.
    """
    try:
        logger.info(f"Generating image for test {test_case.id}...")
        
        # Construct prompt with brand guidelines
        guideline_text = test_case.guidelines.text
        if test_case.guidelines.color_palette:
            guideline_text += f"\nColor Palette: {', '.join(test_case.guidelines.color_palette)}"
        if test_case.guidelines.visual_style:
            guideline_text += f"\nVisual Style: {test_case.guidelines.visual_style}"
            
        full_prompt = (
            f"{test_case.original_prompt}\n\n"
            f"Brand Guidelines:\n{guideline_text}"
        )
        
        response = client.models.generate_images(
            model=model_id,
            prompt=full_prompt,
            config=types.GenerateImagesConfig(
                number_of_images=1,
                aspect_ratio="1:1"
            )
        )
        
        if response.generated_images:
            image_data = response.generated_images[0].image.image_bytes
            output_path = output_dir / f"{test_case.id}.png"
            
            with open(output_path, "wb") as f:
                f.write(image_data)
                
            logger.info(f"Image saved to: {output_path}")
            return output_path
            
        logger.warning(f"No images generated for {test_case.id}")
        return None
        
    except Exception as e:
        logger.error(f"Failed to generate image for {test_case.id}: {e}")
        return None


def main():
    parser = argparse.ArgumentParser(
        description="Run brand evaluation against a golden dataset."
    )
    parser.add_argument(
        "--dataset",
        type=str,
        required=True,
        help="Path to the golden dataset JSON file"
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=80.0,
        help="Minimum pass rate percentage to consider evaluation successful (default: 80)"
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Optional path to save detailed results as JSON"
    )
    parser.add_argument(
        "--eval-model",
        type=str,
        default="gemini-2.5-pro",
        help="Gemini model ID to use for evaluation (default: gemini-2.5-pro)"
    )
    parser.add_argument(
        "--gen-model",
        type=str,
        default="imagen-3.0-generate-001",
        help="Imagen model ID to use for generation (default: imagen-3.0-generate-001)"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose output with detailed results"
    )
    
    args = parser.parse_args()
    
    # Validate dataset path
    dataset_path = Path(args.dataset)
    if not dataset_path.exists():
        logger.error(f"Dataset file not found: {dataset_path}")
        sys.exit(1)
    
    logger.info(f"Loading golden dataset from: {dataset_path}")
    
    try:
        # Initialize clients
        client = GeminiModelSetup.init()
        evaluator = BrandEvaluator(model_id=args.eval_model)
        
        # Load dataset
        golden_dataset = evaluator.load_golden_dataset(str(dataset_path))
        logger.info(f"Found {len(golden_dataset.test_cases)} test cases")
        
        if len(golden_dataset.test_cases) == 0:
            logger.warning("No test cases found in dataset")
            sys.exit(0)
            
        # Create output directory for generated images
        output_dir = Path("generated_images")
        output_dir.mkdir(exist_ok=True)
        
        # Run generation and evaluation
        results = []
        
        for test_case in golden_dataset.test_cases:
            # 1. Generate Image
            generated_image_path = generate_image_for_test_case(
                client, test_case, output_dir, model_id=args.gen_model
            )
            
            if not generated_image_path:
                logger.error(f"Skipping evaluation for {test_case.id} due to generation failure")
                # Fail the test case if generation fails
                results.append(ValidationResult(
                    test_id=test_case.id,
                    image_path="N/A",
                    is_compliant=False,
                    score=0,
                    reasoning="Image generation failed",
                    issues=["Generation failed"],
                    expected_compliant=test_case.expected_compliant
                ))
                continue
            
            # 2. Evaluate Image
            result = evaluator.evaluate_image(test_case, str(generated_image_path))
            results.append(result)
            
        # Compute metrics
        report = evaluator.compute_metrics(results)
        
        # Print summary
        print("\n" + "=" * 60)
        print("BRAND EVALUATION REPORT")
        print("=" * 60)
        print(f"Total Tests:    {report.total_tests}")
        print(f"Passed:         {report.passed_tests}")
        print(f"Failed:         {report.failed_tests}")
        print(f"Pass Rate:      {report.pass_rate:.1f}%")
        print(f"Average Score:  {report.average_score:.1f}/100")
        print(f"Threshold:      {args.threshold}%")
        print("=" * 60)
        
        # Print detailed results if verbose
        if args.verbose:
            print("\nDETAILED RESULTS:")
            print("-" * 60)
            for result in report.results:
                status = "✓ PASS" if result.passed else "✗ FAIL"
                print(f"\n[{status}] Test: {result.test_id}")
                print(f"  Image: {result.image_path}")
                print(f"  Score: {result.score}/100")
                print(f"  Compliant: {result.is_compliant} (Expected: {result.expected_compliant})")
                if result.issues:
                    print(f"  Issues: {', '.join(result.issues)}")
                if args.verbose and result.reasoning:
                    print(f"  Reasoning: {result.reasoning[:200]}...")
        
        # Save results to file if requested
        if args.output:
            output_path = Path(args.output)
            output_data = {
                "summary": {
                    "total_tests": report.total_tests,
                    "passed_tests": report.passed_tests,
                    "failed_tests": report.failed_tests,
                    "pass_rate": report.pass_rate,
                    "average_score": report.average_score,
                    "threshold": args.threshold,
                    "all_passed": report.all_passed,
                },
                "results": [asdict(r) for r in report.results]
            }
            with open(output_path, "w") as f:
                json.dump(output_data, f, indent=2)
            logger.info(f"Results saved to: {output_path}")
        
        # Determine exit code based on threshold
        if report.pass_rate >= args.threshold:
            print(f"\n✓ EVALUATION PASSED (Pass rate {report.pass_rate:.1f}% >= {args.threshold}%)")
            sys.exit(0)
        else:
            print(f"\n✗ EVALUATION FAILED (Pass rate {report.pass_rate:.1f}% < {args.threshold}%)")
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"Evaluation failed with error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
