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
        
        # Agent-as-a-Tool Support: Extract Job ID from message
        if ctx.user_content and ctx.user_content.parts:
            text = ctx.user_content.parts[0].text
            logger.info(f"[{self.name}] Input Text for Job Extraction: {text}")
            import re
            # Match "Job ID: 123" OR "job_id: 123" OR just "123" if context looks like a job id
            match = re.search(r"(?:Job ID|job_id)[:=]?\s*(\d+)", text, re.IGNORECASE)
            if match:
                job_id = int(match.group(1))
                logger.info(f"[{self.name}] Extracted Job ID: {job_id}")
            else:
                logger.warning(f"[{self.name}] Failed to extract Job ID from text.")
                # Fallback: check if the text *is* the job ID?
                if text.strip().isdigit():
                     job_id = int(text.strip())
                     logger.info(f"[{self.name}] Extracted Job ID (direct digit): {job_id}")

        if not job_id:
             yield Event(author=self.name, content=types.Content(parts=[types.Part(text="Skipping validation: No job_id found.")]))
             return

        logger.info(f"[{self.name}] Checking status for Job {job_id}...")
        
        item = await self.media_repo.get_by_id(job_id)
        if not item:
             yield Event(author=self.name, content=types.Content(parts=[types.Part(text="Job not found.")]))
             return
        
        if item.status != JobStatusEnum.COMPLETED:
             yield Event(author=self.name, content=types.Content(parts=[types.Part(text=f"Job status is {item.status}, expected COMPLETED.")]))
             return

        # Proceed to Validate
        yield Event(author=self.name, content=types.Content(parts=[types.Part(text="Generation Complete. validating...")]))
        
        guidelines_text = state.get("guidelines_used", "No explicit guidelines.")
        original_prompt = state.get("original_prompt", "")
        
        from src.agents.dto.agent_validation_dto import AgentValidationResult
        validation_results: list[AgentValidationResult] = []
        
        for uri in item.gcs_uris:
            res = await self.validate_asset(uri, guidelines_text, original_prompt)
            validation_results.append(res)
        
        # Store in state (Dump as dicts for serialization if needed, or keep objects)
        state["validation_report"] = [v.model_dump() for v in validation_results]
        
        # Calculate summary
        compliant_count = sum(1 for r in validation_results if r.is_compliant)
        total = len(validation_results)
        
        summary = f"Validated {total} assets. {compliant_count} Compliant."
        
        # Persist to DB
        try:
            logger.info(f"[{self.name}] Persisting validation results for Job {job_id}...")
            await self.media_repo.update(job_id, {
                "critique": summary,
                "raw_data": {"validations": [v.model_dump() for v in validation_results]}
            })
            logger.info(f"[{self.name}] Persistence complete.")
        except Exception as e:
            logger.error(f"[{self.name}] Failed to persist validation results: {e}")

        # Return the FIRST validation result as the event data for now (or summary)
        # The ADK expects a standardized response.
        ordered_response = {
            "is_compliant": compliant_count == total,
            "score": int((compliant_count / total) * 100) if total > 0 else 0,
            "reasoning": summary,
            "issues": [issue for r in validation_results for issue in r.issues]
        }
        
        yield Event(author=self.name, content=types.Content(parts=[types.Part(text=json.dumps(ordered_response))]))

    async def validate_asset(self, asset_uri: str, guidelines: str, prompt: str) -> 'AgentValidationResult':
        from src.agents.dto.agent_validation_dto import AgentValidationResult
        
        # Re-using logic from original ValidatorAgent
        system_prompt = (
            "You are the Brand Validator Agent.\n"
            "Your task is to audit the provided image against the brand guidelines. "
            "Determine if the image complies with the visual style, color palette, and other rules. "
            "Also check if it faithfully represents the original user prompt.\n\n"
            f"--- BRAND GUIDELINES ---\n{guidelines}\n----------------------\n"
            f"--- ORIGINAL PROMPT ---\n{prompt}\n----------------------\n"
            "Provide your assessment in the following JSON format:\n"
            "  \"is_compliant\": boolean,\n"
            "  \"score\": integer (0-100),\n"
            "  \"reasoning\": \"string explanation with specific sections\",\n"
            "  \"issues\": [\"string list of specific issues found\"]\n"
            "}\n\n"
            "IMPORTANT INSTRUCTIONS FOR 'reasoning' AND 'issues':\n"
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
            mime_type = "image/png"
            if asset_uri.endswith(".mp4"):
                 mime_type = "video/mp4" 
            
            # ADK/GenAI SDK usage
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
                
                data = json.loads(clean_text.strip())
                return AgentValidationResult(**data, raw_response=data)
            
            return AgentValidationResult(
                is_compliant=False, 
                score=0, 
                reasoning="No response from validation model", 
                issues=["Model error"]
            )
        except Exception as e:
            logger.error(f"Validator Gemini call failed: {e}")
            return AgentValidationResult(
                is_compliant=False, 
                score=0, 
                reasoning=f"Validation Execution Failed: {str(e)}", 
                issues=[str(e)]
            )
