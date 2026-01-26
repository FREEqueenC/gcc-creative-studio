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
Brand Evaluator Module

Provides CI/CD-compatible evaluation of generated images against brand guidelines
using Gemini's vision capabilities (LLM-as-a-Judge approach).
"""

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from google.genai import Client, types
from pydantic import BaseModel, Field

from src.config.config_service import config_service
from src.multimodal.schema.gemini_model_setup import GeminiModelSetup

logger = logging.getLogger(__name__)


class Guidelines(BaseModel):
    """Brand guidelines to evaluate against."""
    text: str = Field(description="Full text description of brand guidelines")
    color_palette: List[str] = Field(default_factory=list, description="List of hex color codes")
    visual_style: Optional[str] = Field(default=None, description="Visual style summary")


class TestCase(BaseModel):
    """A single test case in the golden dataset."""
    id: str = Field(description="Unique identifier for this test case")
    reference_image_paths: List[str] = Field(default_factory=list, description="Paths or GCS URIs to reference images (if any)")
    original_prompt: str = Field(description="The prompt used to generate the image")
    guidelines: Guidelines = Field(description="Brand guidelines to check against")
    expected_compliant: bool = Field(default=True, description="Whether this image is expected to be compliant")


class GoldenDataset(BaseModel):
    """The golden dataset containing all test cases."""
    test_cases: List[TestCase] = Field(default_factory=list)


@dataclass
class GuidelineCheck:
    """Result of checking a specific guideline element."""
    criteria: str
    status: str  # "Pass", "Fail", "N/A"
    explanation: str


@dataclass
class ValidationResult:
    """Result of validating a single image against brand guidelines."""
    test_id: str
    image_path: str
    is_compliant: bool
    score: int  # 0-100
    reasoning: str
    issues: List[str] = field(default_factory=list)
    guideline_checks: List[GuidelineCheck] = field(default_factory=list)
    expected_compliant: bool = True
    passed: bool = False  # True if result matches expectation
    
    def __post_init__(self):
        self.passed = self.is_compliant == self.expected_compliant


@dataclass
class EvaluationReport:
    """Aggregate report of all evaluation results."""
    total_tests: int = 0
    passed_tests: int = 0
    failed_tests: int = 0
    average_score: float = 0.0
    results: List[ValidationResult] = field(default_factory=list)
    
    @property
    def pass_rate(self) -> float:
        if self.total_tests == 0:
            return 0.0
        return (self.passed_tests / self.total_tests) * 100
    
    @property
    def all_passed(self) -> bool:
        return self.failed_tests == 0 and self.total_tests > 0


class BrandEvaluator:
    """
    Evaluates generated images against brand guidelines using Gemini's vision capabilities.
    
    This class implements the "LLM-as-a-Judge" approach from the design document
    for CI/CD evaluation of image compliance.
    """
    
    def __init__(self, model_id: Optional[str] = None):
        """
        Initialize the BrandEvaluator.
        
        Args:
            model_id: Optional Gemini model ID. Defaults to gemini-2.5-pro.
        """
        self.client: Client = GeminiModelSetup.init()
        self.model_id = model_id or "gemini-2.5-pro"
        logger.info(f"BrandEvaluator initialized with model: {self.model_id}")
    
    def _build_evaluation_prompt(self, guidelines: Guidelines, original_prompt: str) -> str:
        """Build the evaluation prompt for the LLM-as-a-Judge."""
        guideline_parts = [guidelines.text]
        
        if guidelines.color_palette:
            colors = ", ".join(guidelines.color_palette)
            guideline_parts.append(f"Color Palette: {colors}")
        
        if guidelines.visual_style:
            guideline_parts.append(f"Visual Style: {guidelines.visual_style}")
        
        guidelines_text = "\n".join(guideline_parts)
        
        prompt = (
            "You are the Brand Validator Agent. Your task is to audit the provided image against the following brand guidelines.\n"
            "Determine if the image complies with the visual style, color palette, and other rules.\n"
            "Also check if it faithfully represents the original user prompt.\n\n"
            f"--- BRAND GUIDELINES ---\n{guidelines_text}\n----------------------\n\n"
            f"--- ORIGINAL PROMPT ---\n{original_prompt}\n----------------------\n\n"
            "Provide your assessment in the following JSON format:\n"
            "{\n"
            '  "is_compliant": boolean,\n'
            '  "score": integer (0-100),\n'
            '  "reasoning": "string explanation",\n'
            '  "issues": ["list", "of", "issues"],\n'
            '  "guideline_checks": [\n'
            '    {\n'
            '      "criteria": "string (e.g. Color Palette)",\n'
            '      "status": "Pass" | "Fail" | "N/A",\n'
            '      "explanation": "why it passed or failed"\n'
            '    }\n'
            '  ]\n'
            "}\n\n"
            "IMPORTANT INSTRUCTIONS:\n"
            "1.  Break down the guidelines into specific checks (e.g., Color Accuracy, Subject Visibility, Style Match).\n"
            "2.  For each check, provide a status and a brief explanation.\n"
            "3.  The 'score' should reflect the overall compliance.\n"
            "4.  List main violations in 'issues'.\n"
        )
        return prompt
    
    def _get_mime_type(self, image_path: str) -> str:
        """Determine MIME type from file extension."""
        path_lower = image_path.lower()
        if path_lower.endswith((".jpg", ".jpeg")):
            return "image/jpeg"
        elif path_lower.endswith(".png"):
            return "image/png"
        elif path_lower.endswith(".gif"):
            return "image/gif"
        elif path_lower.endswith(".webp"):
            return "image/webp"
        return "image/png"  # Default
    
    def _load_image_part(self, image_path: str) -> types.Part:
        """Load an image as a Part object for Gemini."""
        if image_path.startswith("gs://"):
            # GCS URI
            return types.Part.from_uri(
                file_uri=image_path, 
                mime_type=self._get_mime_type(image_path)
            )
        else:
            # Local file
            local_path = Path(image_path)
            if not local_path.exists():
                raise FileNotFoundError(f"Image not found: {image_path}")
            
            with open(local_path, "rb") as f:
                image_bytes = f.read()
            
            return types.Part.from_bytes(
                data=image_bytes,
                mime_type=self._get_mime_type(image_path)
            )
    
    def evaluate_image(
        self, 
        test_case: TestCase,
        image_path: str
    ) -> ValidationResult:
        """
        Evaluate a single image against brand guidelines.
        
        Args:
            test_case: The test case containing guidelines and expectations.
            image_path: Path to the image to evaluate (generated or original).
            
        Returns:
            ValidationResult with compliance status, score, and reasoning.
        """
        logger.info(f"Evaluating test case: {test_case.id} with image: {image_path}")
        
        try:
            image_part = self._load_image_part(image_path)
            prompt = self._build_evaluation_prompt(
                test_case.guidelines, 
                test_case.original_prompt
            )
            
            response = self.client.models.generate_content(
                model=self.model_id,
                contents=[image_part, prompt],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json"
                )
            )
            
            if response.text:
                result_data = json.loads(response.text)
                logger.info(f"Test {test_case.id}: score={result_data.get('score', 0)}, compliant={result_data.get('is_compliant', False)}")
                
                # Parse guideline checks
                guideline_checks_data = result_data.get("guideline_checks", [])
                guideline_checks = [
                    GuidelineCheck(**check) for check in guideline_checks_data
                ]
                
                return ValidationResult(
                    test_id=test_case.id,
                    image_path=image_path,
                    is_compliant=result_data.get("is_compliant", False),
                    score=result_data.get("score", 0),
                    reasoning=result_data.get("reasoning", ""),
                    issues=result_data.get("issues", []),
                    guideline_checks=guideline_checks,
                    expected_compliant=test_case.expected_compliant,
                )
            
            logger.warning(f"Test {test_case.id}: Empty response from model")
            return ValidationResult(
                test_id=test_case.id,
                image_path=image_path,
                is_compliant=False,
                score=0,
                reasoning="No response from model",
                issues=["Model returned empty response"],
                expected_compliant=test_case.expected_compliant,
            )
            
        except Exception as e:
            logger.error(f"Test {test_case.id} failed: {e}")
            return ValidationResult(
                test_id=test_case.id,
                image_path=image_path,
                is_compliant=False,
                score=0,
                reasoning=f"Evaluation error: {e}",
                issues=[str(e)],
                expected_compliant=test_case.expected_compliant,
            )
    
    def evaluate_golden_dataset(self, dataset: GoldenDataset) -> EvaluationReport:
        """
        Evaluate all test cases in a golden dataset using their original images.
        
        Args:
            dataset: The golden dataset with all test cases.
            
        Returns:
            EvaluationReport with aggregate results.
        """
        results: List[ValidationResult] = []
        
        for test_case in dataset.test_cases:
            # Fallback to evaluating the original image if this method is called directly
            result = self.evaluate_image(test_case, test_case.original_image_path)
            results.append(result)
        
        return self.compute_metrics(results)
    
    def compute_metrics(self, results: List[ValidationResult]) -> EvaluationReport:
        """Compute aggregate metrics from validation results."""
        if not results:
            return EvaluationReport()
        
        passed = sum(1 for r in results if r.passed)
        failed = len(results) - passed
        avg_score = sum(r.score for r in results) / len(results)
        
        return EvaluationReport(
            total_tests=len(results),
            passed_tests=passed,
            failed_tests=failed,
            average_score=avg_score,
            results=results,
        )
    
    @staticmethod
    def load_golden_dataset(path: str) -> GoldenDataset:
        """
        Load a golden dataset from a JSON file.
        
        Args:
            path: Path to the JSON file.
            
        Returns:
            Parsed GoldenDataset.
        """
        with open(path, "r") as f:
            data = json.load(f)
        return GoldenDataset(**data)
