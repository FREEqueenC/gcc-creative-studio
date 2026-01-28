import logging
import asyncio
from enum import Enum
from typing import Dict, Any, List, AsyncGenerator
from fastapi import Depends, BackgroundTasks

# ADK Imports
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.agents import SequentialAgent
from google.adk.events.event import Event
from google.genai import types

# Backend Imports
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
from src.agents.adk.enforcer import BrandingEnforcerADK
# from src.agents.adk.generator import MediaGeneratorADK
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
        self.vector_search_service = vector_search_service
        self.gemini_service = gemini_service
        
        # Initialize ADK Agents
        # Note: In a real app, these might be singletons or factory-created.
        self.enforcer = BrandingEnforcerADK(
            name="BrandingEnforcer",
            vector_search_service=vector_search_service,
            gemini_service=gemini_service,
            brand_guideline_repo=brand_guideline_repo
        )
        
        # self.generator is removed in favor of MediaGenerationToolWrapper instantiated per request
        # self.generator = MediaGeneratorADK(...)
        
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
        current_user: UserModel,
        background_tasks: BackgroundTasks
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
        
        # Prepare Tool Wrapper (needs to be created here to capture services)
        from src.agents.tools.media_generation_tool import MediaGenerationToolWrapper
        # Note: We pass current_user, but technically in background it might be detached? 
        # SQLAlchemy objects used in background tasks need care. 
        # But here we just pass the object for ID access. Data access might fail if session closed.
        # Ideally, pass primitive ID and reload user in background if needed.
        # For now, we assume `current_user` is a Pydantic model or detached ORM object?
        # It is `UserModel` (Pydantic/ORM hybrid or just ORM). 
        # If it's ORM attached to a request session, accessing it in background might fail.
        # Safest: Pass necessary data explicitly or merge.
        # But `AgentGenerationRequest` has everything.
        
        # We start the background task
        background_tasks.add_task(
            self._run_director_background,
            request=request,
            user=current_user,
            session_id=session_id,
            state=state
        )
        
        logger.info(f"Agentic flow started in background. Session: {session_id}")
        
        # Return immediate response (Pending)
        return AgentGenerationResponse(
            original_prompt=request.prompt,
            enhanced_prompt="Processing...",
            generated_assets=[],
            session_id=session_id
        )

    async def _run_director_background(self, request: AgentGenerationRequest, user: UserModel, session_id: str, state: Dict[str, Any]):
        """
        Background task to run the Deterministic Media Pipeline.
        """
        from src.database import AsyncSessionLocal
        from src.images.repository.media_item_repository import MediaRepository
        
        # Create a fresh DB session for the background task
        async with AsyncSessionLocal() as session:
            try:
                logger.info(f"[_run_director_background] Starting for {session_id}")
                
                # Setup Repo
                media_repo = MediaRepository(session)
                
                # Setup Components with fresh repo
                # Validator needs the fresh repo for polling
                validator = ValidatorADK(
                    name="Validator",
                    gemini_service=self.validator_adk.gemini_service, # Reuse service
                    media_repo=media_repo
                )
                
                # Patch services with fresh repo
                # This ensures the Generator tool uses the active session
                # Ideally, we should refactor services to accept repo per call or be request-scoped properly in BG tasks.
                # For now, this patch pattern mimics the previous working solution.
                self.imagen_service.media_repo = media_repo
                self.veo_service.media_repo = media_repo
                self.audio_service.media_repo = media_repo
                
                # Initialize MediaGeneratorADK
                # We do NOT use the wrapper here anymore, we use the Agent directly
                # However, MediaGeneratorADK needs the services.
                from src.agents.adk.generator import MediaGeneratorADK
                generator_agent = MediaGeneratorADK(
                    name="MediaGenerator",
                    imagen_service=self.imagen_service,
                    veo_service=self.veo_service,
                    audio_service=self.audio_service
                )
                
                # Initialize JobPollerADK
                from src.agents.adk.poller import JobPollerADK
                poller_agent = JobPollerADK(
                    name="JobPoller",
                    media_repo=media_repo
                )
                
                # Enforcer (Reuse instance as it is service-based, but ensure its services are safe)
                # Enforcer uses VectorSearch/Gemini which are generally stateless/http-based or handle their own sessions
                # If Enforcer uses BrandGuidelineRepository, we might need to patch that too if it uses DB.
                # It does! `brand_guideline_repo` in `__init__`.
                # We need to make sure `self.enforcer` works.
                # Actually `self.enforcer` was created with `Depends(BrandGuidelineRepository)`.
                # If that repo depends on `Depends(get_db)`, it might be closed.
                # Safest bet: Re-create Enforcer with fresh repo if needed.
                # `BrandGuidelineRepository` is just SQLalchemy wrapper.
                
                # Let's check `self.enforcer.brand_guideline_repo`.
                # If it's closed, we need a new one.
                # To be Robust: Re-create Enforcer.
                from src.brand_guidelines.repository.brand_guideline_repository import BrandGuidelineRepository
                bg_repo = BrandGuidelineRepository(session)
                # Re-create Enforcer with fresh BG Repo
                # We can reuse the services (Vector/Gemini) as they are likely safe
                enforcer = BrandingEnforcerADK(
                    name="BrandingEnforcer",
                    vector_search_service=self.vector_search_service,
                    gemini_service=self.gemini_service,
                    brand_guideline_repo=bg_repo 
                )
                
                from src.agents.adk.manager import create_media_pipeline
                
                pipeline = create_media_pipeline(enforcer, generator_agent, poller_agent, validator)
                
                await self.session_service.create_session(
                    app_name="adk",
                    user_id=user.email,
                    session_id=session_id,
                    state=state
                )
                
                pipeline_runner = Runner(
                    agent=pipeline,
                    app_name="adk",
                    session_service=self.session_service
                )
                
                # Start the pipeline
                # The SequentialAgent runs the sub-agents in order.
                # We don't need a prompt really, just a kick-off.
                # But Enforcer expects `original_prompt` in context/message to find guidelines.
                # Enforcer instruction: "1. CHECK the context for `workspace_id` and the user's `original_prompt`."
                
                # We send the actual instructions as the first message to kick off the Enforcer.
                # The Enforcer's system prompt expects: "1. CHECK the context for `workspace_id` and the user's `original_prompt`."
                # However, LlmAgents respond better to direct instructions in the message history.
                
                start_instruction = (
                    f"Please enforce guidelines for the following request:\n"
                    f"Workspace ID: {state.get('workspace_id')}\n"
                    f"Prompt: {state.get('original_prompt')}\n"
                    f"Media Type: {state.get('media_type')}"
                )
                
                trigger_msg = types.Content(role="user", parts=[types.Part(text=start_instruction)])
                
                async for event in pipeline_runner.run_async(user_id=user.email, session_id=session_id, new_message=trigger_msg):
                    logger.info(f"[Pipeline Event] {event.author}: {event}")
                    
                    # Publish relevant events to frontend
                    if event.content and event.content.parts:
                         text = event.content.parts[0].text
                         if text:
                             # 1. Pass through the original event
                             await self.event_bus.publish(f"user_{user.email}", event)
                             
                             # 2. Check for Job ID signal from MediaGenerator to unblock Frontend
                             # Format: "Generation started. Job ID: <id>"
                             if "Generation started. Job ID:" in text:
                                try:
                                    job_id_str = text.split("Job ID:")[-1].strip()
                                    if job_id_str.isdigit():
                                        # Emit the legacy System event that the frontend expects
                                        sys_event = Event(
                                            author="System",
                                            content=types.Content(
                                                parts=[types.Part(text=f"Captured Long Running Job ID: {job_id_str}")]
                                            )
                                        )
                                        await self.event_bus.publish(f"user_{user.email}", sys_event)
                                        logger.info(f"Published legacy System event for Job ID: {job_id_str}")
                                except Exception as e:
                                    logger.warning(f"Failed to parse Job ID for legacy event: {e}")

            except Exception as e:
                logger.error(f"Background ADK Pipeline Failed: {e}", exc_info=True)
                # Publish error event to user
                await self.event_bus.publish(f"user_{user.email}", Event(author="System", content=types.Content(parts=[types.Part(text=f"Agent process failed: {str(e)}")]) ))


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
