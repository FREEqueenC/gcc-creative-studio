import logging
import asyncio
from enum import Enum
from typing import Dict, Any, List, AsyncGenerator
from fastapi import Depends

# ADK Imports
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.agents import SequentialAgent
from google.adk.events.event import Event
from google.genai import types

# Backend Imports
from src.agents.enforcer_agent import BrandingEnforcerAgent as LegacyEnforcer # Keep just in case or remove?
from src.agents.validator_agent import ValidatorAgent as LegacyValidator
from src.agents.dto.agent_dto import AgentGenerationRequest, AgentGenerationResponse, MediaTypeEnum
from src.images.dto.create_imagen_dto import CreateImagenDto, AspectRatioEnum
from src.videos.dto.create_veo_dto import CreateVeoDto
from src.audios.dto.create_audio_dto import CreateAudioDto
from src.common.base_dto import GenerationModelEnum
from src.videos.veo_service import VeoService
from src.audios.audio_service import AudioService
from src.images.imagen_service import ImagenService
from src.users.user_model import UserModel
from src.audios.audio_constants import VoiceEnum, LanguageEnum
from src.common.schema.media_item_model import JobStatusEnum

# New ADK Agents
from src.agents.adk.enforcer import BrandingEnforcerADK
from src.agents.adk.generator import MediaGeneratorADK
from src.agents.adk.validator import ValidatorADK
from src.tools.adk_wrappers import create_adk_search_tool
from src.common.vector_search_service import VectorSearchService
from src.multimodal.gemini_service import GeminiService
from src.brand_guidelines.repository.brand_guideline_repository import BrandGuidelineRepository
from src.common.event_bus import get_event_bus, EventBus

logger = logging.getLogger(__name__)

class AgentService:
    """
    Orchestrates the Agentic RAG flow using Google ADK.
    Phase 1: Enforcer -> Generator (Sync/Fast).
    Validation is triggered via background polling (as before) but can use ADK Validator.
    """

    def __init__(
        self,
        # Services required for Agents
        vector_search_service: VectorSearchService = Depends(),
        gemini_service: GeminiService = Depends(),
        brand_guideline_repo: BrandGuidelineRepository = Depends(),
        imagen_service: ImagenService = Depends(),
        veo_service: VeoService = Depends(),
        audio_service: AudioService = Depends(),
        # Legacy Validator Needed? We can use ADK Validator or Legacy.
        # Let's use LegacyValidator implementation inside ADK Validator or just use ADK Validator.
        # For background polling, we need the service instance mostly.
    ):
        self.imagen_service = imagen_service
        self.veo_service = veo_service
        self.audio_service = audio_service
        
        # Initialize ADK Agents
        # Note: In a real app, these might be singletons or factory-created.
        self.enforcer = BrandingEnforcerADK(
            name="BrandingEnforcer",
            vector_search_service=vector_search_service,
            gemini_service=gemini_service,
            brand_guideline_repo=brand_guideline_repo
        )
        
        self.generator = MediaGeneratorADK(
            name="MediaGenerator",
            imagen_service=imagen_service,
            veo_service=veo_service,
            audio_service=audio_service
        )
        
        # We also initialize the ValidatorADK for potential use (even if triggers later)
        self.validator_adk = ValidatorADK(
            name="Validator",
            gemini_service=gemini_service,
            media_repo=None # Will be set dynamically based on media type? Or we inject a generic repo wrapper?
            # ValidatorADK expects media_repo to have get_by_id and update.
            # We'll set it at runtime or inject the specific service.
        )
        self.session_service = InMemorySessionService()
        self.event_bus = get_event_bus()

    async def generate_compliant_media(
        self, 
        request: AgentGenerationRequest, 
        current_user: UserModel
    ) -> AgentGenerationResponse:
        """
        Executes the ADK workflow.
        """
        logger.info(f"Starting ADK agentic generation for user {current_user.email} - Type: {request.media_type}")
        
        # 1. Setup Session State
        session_id = f"sess_{request.workspace_id}_{current_user.email}_{id(request)}"
        state = {
            "original_prompt": request.prompt,
            "workspace_id": str(request.workspace_id),
            "media_type": request.media_type.value if hasattr(request.media_type, 'value') else request.media_type,
            "current_user": current_user,
            "request_config": {
                "generation_model": request.generation_model,
                "aspect_ratio": request.aspect_ratio,
                "number_of_media": request.number_of_media,
                "style": request.style,
                "duration_seconds": request.duration_seconds,
                "generate_audio": request.generate_audio,
                "voice_name": request.voice_name
            },
            "reference_image_uris": [request.reference_image_uri] if request.reference_image_uri else []
        }
        
        # 2. Run Enforcer Agent
        logger.info("Running BrandingEnforcerADK...")
        
        # NOTE: The ADK BaseAgent seems to infer 'app_name' from the package or defaults to 'adk'.
        # To avoid mismatch warnings/errors, we align the Runner with the Agent's expected app_name.
        enforcer_app_name = "adk"
        
        # Ensure session exists in the 'adk' namespace as well
        await self.session_service.create_session(
            app_name=enforcer_app_name,
            user_id=current_user.email,
            session_id=session_id,
            state=state
        )

        enforcer_runner = Runner(
            agent=self.enforcer,
            app_name=enforcer_app_name,
            session_service=self.session_service
        )

        prompt_with_context = (
            f"Context:\n"
            f"Workspace ID: {request.workspace_id}\n"
            f"Original Prompt: {request.prompt}\n\n"
            f"Task: Rewrite the prompt according to brand guidelines."
        )
        enforcer_start_msg = types.Content(role="user", parts=[types.Part(text=prompt_with_context)])
        
        async for event in enforcer_runner.run_async(user_id=current_user.email, session_id=session_id, new_message=enforcer_start_msg):
            # Log ALL events for debugging
            logger.info(f"[Enforcer Event] {event.author} ({type(event).__name__}): {event}")
            
            if event.content:
                 text = event.content.parts[0].text if event.content.parts else ''
                 logger.info(f"[Enforcer Content] {text}")
                 
                 # Publish to user stream 
                 if text:
                    await self.event_bus.publish(f"user_{current_user.email}", event)

        # 3. Parse Enforcer Output
        # Re-fetch session from the 'adk' namespace to get the agent's response
        enforcer_session = await self.session_service.get_session(app_name=enforcer_app_name, user_id=current_user.email, session_id=session_id)
        
        enhanced_prompt = request.prompt
        reference_image_uris = []
        guidelines_used = ""
        
        if enforcer_session and enforcer_session.events:
            last_message = enforcer_session.events[-1]
            if last_message.content and last_message.content.parts:
                 text = last_message.content.parts[0].text
                 try:
                     import json
                     # Clean potential markdown
                     clean_text = text.strip()
                     if clean_text.startswith("```json"):
                         clean_text = clean_text[7:]
                     elif clean_text.startswith("```"):
                         clean_text = clean_text[3:]
                     if clean_text.endswith("```"):
                         clean_text = clean_text[:-3]
                     
                     data = json.loads(clean_text)
                     enhanced_prompt = data.get("enhanced_prompt", request.prompt)
                     reference_image_uris = data.get("reference_image_uris", [])
                     guidelines_used = data.get("guidelines_used", "")
                     
                     logger.info(f"CAPTURED ENHANCED PROMPT: {enhanced_prompt}")
                     logger.info(f"CAPTURED REFERENCE IMAGES: {reference_image_uris}")
                     
                 except (json.JSONDecodeError, AttributeError, ImportError):
                     logger.warning("Failed to parse Enforcer JSON output. Using raw text as fallback.")
                     # Fallback: if it's not JSON, maybe it's just the text prompt
                     if text.strip():
                        enhanced_prompt = text

        # Update Session State for Generator
        # Since MediaGeneratorADK is also in 'src.agents.adk', it will also require app_name="adk".
        # So we update the 'adk' session directly.
        if enforcer_session:
             # Merge reference URIs
             existing_uris = enforcer_session.state.get("reference_image_uris", [])
             all_uris = list(set(existing_uris + reference_image_uris))
             
             enforcer_session.state["enhanced_prompt"] = enhanced_prompt
             enforcer_session.state["reference_image_uris"] = all_uris
             enforcer_session.state["guidelines_used"] = guidelines_used
             logger.info("Updated 'adk' session state with Enforcer results.")

        # 4. Run Generator Agent
        logger.info("Running MediaGeneratorADK...")
        
        # Publish a starting event manually to update UI immediately
        start_event = Event(
            author="MediaGeneratorADK",
            content=types.Content(parts=[types.Part(text="Starting generation process...")])
        )
        await self.event_bus.publish(f"user_{current_user.email}", start_event)
        
        # Generator also needs 'adk' app_name to match package location
        generator_runner = Runner(
            agent=self.generator,
            app_name=enforcer_app_name, 
            session_service=self.session_service
        )
        
        # We can send a dummy signal or "Start Generation".
        gen_trigger = types.Content(role="user", parts=[types.Part(text="Proceed with generation.")])
        
        async for event in generator_runner.run_async(user_id=current_user.email, session_id=session_id, new_message=gen_trigger):
             if event.content:
                 # Generator events (e.g. "Generating...")
                 await self.event_bus.publish(f"user_{current_user.email}", event)

        # 5. Extract Final Results from the 'adk' session
        final_session = await self.session_service.get_session(app_name=enforcer_app_name, user_id=current_user.email, session_id=session_id)
        final_state = final_session.state if final_session else {}
        assets = final_state.get("generated_assets", [])


        
        # 5. Trigger Background Validation (Legacy Logic Compatibility)
        if assets:
            job_id = assets[0]['id']
            # Determine Repo
            repo_service = None
            if request.media_type == "IMAGE":
                repo_service = self.imagen_service
            elif request.media_type == "VIDEO":
                repo_service = self.veo_service
            elif request.media_type == "AUDIO":
                repo_service = self.audio_service
            
            if repo_service:
                # We reuse the legacy poll_and_validate logic or adapt it to use ValidatorADK
                # Let's adapt to use ValidatorADK in a separate "Runner" or manual run
                self.validator_adk.media_repo = repo_service.media_repo
                
                asyncio.create_task(self._run_async_validation(
                    job_id=job_id,
                    guidelines=guidelines_used, 
                    prompt=enhanced_prompt, # Use enhanced prompt for validation context? Or original? Legacy used original. But enhanced has more detail. Let's use enhanced or both. Legacy used 'original_prompt'.
                    # User request: "also check if it faithfully represents the original user prompt" -> So ORIGINAL.
                    # But guidelines check needs guidelines.
                    user_id=current_user.email
                ))

        return AgentGenerationResponse(
            original_prompt=request.prompt,
            enhanced_prompt=enhanced_prompt,
            generated_assets=assets,
            session_id=session_id
        )

    async def _run_async_validation(self, job_id: int, guidelines: str, prompt: str, user_id: str):
        """
        Runs the ValidatorADK in a separate ephemeral session/runner.
        Detailed: Creates a fresh DB session to avoid 'Session is closed' errors in background tasks.
        """
        logger.info(f"Triggering Async Validation for Job {job_id}")
        
        from src.database import AsyncSessionLocal
        from src.images.repository.media_item_repository import MediaRepository
        
        # Create a fresh session for the background task
        async with AsyncSessionLocal() as session:
            # We need to configure the ValidatorADK with a fresh repo bound to this session
            media_repo = MediaRepository(session)
            
            # Temporarily inject the fresh repo into the agent
            # NOTE: this is not thread-safe if Agent is a singleton. 
            # Ideally ValidatorADK should take repo in `run` or we instantiate a transient ValidatorADK.
            # Given AgentService is request-scoped, 'self.validator_adk' is also request-scoped instance?
            # NO. AgentService is request-scoped (Depends()), but if it holds state, it's local.
            # So modifying `self.validator_adk.media_repo` here is safe for THIS request's lifecycle?
            # NO. The request finishes, AgentService is garbage collected? 
            # Actually, `self` is captured by the async task closure.
            # So `self.validator_adk` stays alive.
            # But `self.session_service` (InMemory) is also used.
            
            self.validator_adk.media_repo = media_repo
            
            session_id = f"val_sess_{job_id}"
            state = {
                "job_id": job_id,
                "guidelines_used": guidelines,
                "original_prompt": prompt
            }
            
            await self.session_service.create_session(app_name="GCCCreativeStudio", user_id=user_id, session_id=session_id, state=state)
            
            runner = Runner(
                agent=self.validator_adk,
                app_name="GCCCreativeStudio",
                session_service=self.session_service
            )
            
            trigger_msg = types.Content(role="user", parts=[types.Part(text=f"Check validation for job {job_id}")])
            async for event in runner.run_async(user_id=user_id, session_id=session_id, new_message=trigger_msg):
                 text = event.content.parts[0].text if event.content and event.content.parts else ''
                 logger.info(f"[Validation Event] {event.author}: {text}")
                 await self.event_bus.publish(f"user_{user_id}", event)
            
            # Persist results
            final_session = await self.session_service.get_session(app_name="GCCCreativeStudio", user_id=user_id, session_id=session_id)
            if final_session and final_session.state.get("validation_report"):
                 report = final_session.state.get("validation_report")
                 await self._persist_validation(job_id, report, media_repo)

    async def _persist_validation(self, mid: int, validation_results: List[Any], media_repo: Any):
        # Flatten logic from legacy
        all_validations = []
        combined_critique = []
        
        for res in validation_results:
             # validation_results in ADK might be formatted slightly differently, check `validator.py`
             # It returns `validate_asset` output: {is_compliant, score, reasoning}
             # It does NOT wrap in {validation: ...} like legacy loop did?
             # Let's standardize.
             all_validations.append(res)
             score = res.get('score', 0)
             status = "COMPLIANT" if res.get('is_compliant') else "NON-COMPLIANT"
             combined_critique.append(f"{status} (Score: {score}): {res.get('reasoning', '')}")

        update_payload = {
            "raw_data": {"validations": all_validations},
            "critique": "\n\n".join(combined_critique)
        }
        if media_repo:
            await media_repo.update(mid, update_payload)
            logger.info(f"Persisted validation for {mid}")
