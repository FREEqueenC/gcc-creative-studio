import logging
import asyncio
import json
from typing import AsyncGenerator, Any

from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event
from google.genai import types

from src.multimodal.gemini_service import GeminiService
from src.common.base_dto import GenerationModelEnum
from src.common.schema.media_item_model import JobStatusEnum

logger = logging.getLogger(__name__)

from pydantic import PrivateAttr

class ValidatorADK(BaseAgent):
    """
    ADK Agent for validating generated assets.
    """
    _gemini_service: Any = PrivateAttr()
    _media_repo: Any = PrivateAttr()
    
    def __init__(self, name: str, gemini_service: GeminiService, media_repo: Any):
        super().__init__(name=name)
        self._gemini_service = gemini_service
        self._media_repo = media_repo

    @property
    def gemini_service(self):
        return self._gemini_service

    @property
    def media_repo(self):
        return self._media_repo
    
    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        state = ctx.session.state
        job_id = state.get("job_id")
        
        if not job_id:
             yield Event(author=self.name, content=types.Content(parts=[types.Part(text="Skipping validation: No job_id found.")]))
             return

        # TODO: In a real Loop, we need to WAIT for the job to complete.
        # For Phase 1 (Async), we might just check status and exit if not ready,
        # forcing the orchestrator to handle the waiting/polling.
        # OR we can implement a simple poll here if this agent is expected to block.
        # Given "Realtime Updates", blocking here and yielding status events is good.
        
        logger.info(f"[{self.name}] Checking status for Job {job_id}...")
        
        # Poll for completion (Simple implementation for demonstration)
        # Timeout after 60s for demo? Or rely on background task.
        max_retries = 30
        for i in range(max_retries):
            item = await self.media_repo.get_by_id(job_id)
            if not item:
                 yield Event(author=self.name, content=types.Content(parts=[types.Part(text="Job not found.")]))
                 return
            
            if item.status == JobStatusEnum.COMPLETED:
                break
            if item.status == JobStatusEnum.FAILED:
                 yield Event(author=self.name, content=types.Content(parts=[types.Part(text="Generation Checked: FAILED.")]))
                 return
            
            if i % 5 == 0:
                 yield Event(author=self.name, content=types.Content(parts=[types.Part(text=f"Waiting for generation... ({i*2}s)")]))
            
            await asyncio.sleep(2)
        else:
             yield Event(author=self.name, content=types.Content(parts=[types.Part(text="Validation timed out waiting for generation.")]))
             return

        # Proceed to Validate
        yield Event(author=self.name, content=types.Content(parts=[types.Part(text="Generation Complete. validating...")]))
        
        guidelines_text = state.get("guidelines_used", "No explicit guidelines.")
        original_prompt = state.get("original_prompt", "")
        
        validation_results = []
        for uri in item.gcs_uris:
            res = await self.validate_asset(uri, guidelines_text, original_prompt)
            validation_results.append(res)
        
        # Store in state
        state["validation_report"] = validation_results
        
        # Calculate summary
        compliant_count = sum(1 for r in validation_results if r.get("is_compliant"))
        total = len(validation_results)
        
        summary = f"Validated {total} assets. {compliant_count} Compliant."
        yield Event(author=self.name, content=types.Content(parts=[types.Part(text=summary)]))

    async def validate_asset(self, asset_uri: str, guidelines: str, prompt: str) -> dict:
        # Re-using logic from original ValidatorAgent
        # We construct the multimodal prompt
        system_prompt = (
            "You are the Brand Validator Agent.\n"
            "Your task is to audit the provided image against the brand guidelines. "
            "Determine if the image complies with the visual style, color palette, and other rules. "
            "Also check if it faithfully represents the original user prompt.\n\n"
            f"--- BRAND GUIDELINES ---\n{guidelines}\n----------------------\n"
            f"--- ORIGINAL PROMPT ---\n{prompt}\n----------------------\n"
            "Provide your assessment in the following JSON format:\n"
            "{\n"
            "  \"is_compliant\": boolean,\n"
            "  \"score\": integer (0-100),\n"
            "  \"reasoning\": \"string explanation with specific sections\"\n"
            "}\n\n"
            "IMPORTANT INSTRUCTIONS FOR 'reasoning':\n"
            "1. Use a clean, structured format.\n"
            "2. Use standard ASCII formatting for lists (e.g., '•' or '-') and capitalization for headers.\n"
            "3. Example Format:\n"
            "   COMPLIANCE ANALYSIS:\n"
            "   • Score: 85/100\n"
            "   • Status: Non-Compliant\n"
            "   KEY FINDINGS:\n"
            "   • The image adheres to the color palette.\n"
            "   • VIOLATION: The logo placement is incorrect."
        )
        
        try:
            # We need to handle image types.
            mime_type = "image/png"
            if asset_uri.endswith(".mp4"):
                 mime_type = "video/mp4" # Gemini 2.5 supports video
            
            image_part = types.Part.from_uri(file_uri=asset_uri, mime_type=mime_type)
            
            response = await self.gemini_service.client.aio.models.generate_content(
                model=GenerationModelEnum.GEMINI_2_5_PRO,
                contents=[image_part, system_prompt],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json"
                )
            )
            
            if response.text:
                clean_text = response.text.strip()
                if clean_text.startswith("```json"):
                    clean_text = clean_text[7:]
                elif clean_text.startswith("```"):
                    clean_text = clean_text[3:]
                if clean_text.endswith("```"):
                    clean_text = clean_text[:-3]
                return json.loads(clean_text.strip())
            return {"is_compliant": False, "score": 0, "reasoning": "No response"}
        except Exception as e:
            logger.error(f"Validator Gemini call failed: {e}")
            return {"is_compliant": False, "score": 0, "reasoning": str(e)}
