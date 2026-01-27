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
        Background task to run the Creative Director Flow.
        """
        from src.database import AsyncSessionLocal
        from src.images.repository.media_item_repository import MediaRepository
        
        # Create a fresh DB session for the background task
        async with AsyncSessionLocal() as session:
            try:
                logger.info(f"[_run_director_background] Starting for {session_id}")
                
                # Setup Repo
                media_repo = MediaRepository(session)
                
                # Setup Tools with fresh repo
                # Validator needs the repo
                # We create a fresh validator for this background run to avoid state issues
                validator = ValidatorADK(
                    name="Validator",
                    gemini_service=self.validator_adk.gemini_service, # Reuse service
                    media_repo=media_repo
                )
                
                # Generator Tool Wrapper (needs user)
                # Note: The usage of self.imagen_service inside this wrapper might still be problematic 
                # if inside it uses a closed DB session. 
                # HOWEVER, ImagenService usually does `repo = ...`. 
                # If ImagenService was initialized with a Repo that depends on a closed session, it will fail.
                # `AgentService` gets `imagen_service` from `Depends`.
                # We might need to "Patch" the repo in `imagen_service` too?
                # or create a new `ImagenService`?
                # For `start_generation`, it calls `media_repo.create`.
                # We should probably inject the FRESH `media_repo` into the `MediaGenerationToolWrapper`?
                # BUT `MediaGenerationToolWrapper` takes `ImagenService`.
                # Let's hope `ImagenService` is stateless regarding DB session OR we patch it.
                # Actually `ImagenService` has `self.media_repo`.
                # We MUST patch it.
                
                # Patch services with fresh repo (Hack but necessary for BackgroundTasks with Depends pattern)
                # Ideally we factories everything.
                self.imagen_service.media_repo = media_repo
                # Veo/Audio services also need repos? Assuming image for now or generic media repo works for all?
                # If they use different repos, we need to recreate them too. 
                # For now, let's assume they share or we just patch imagen as partial fix.
                # Actually, `MediaRepository` handles `media_items` table which is shared.
                
                from src.agents.tools.media_generation_tool import MediaGenerationToolWrapper
                gen_tool_wrapper = MediaGenerationToolWrapper(
                    self.imagen_service, 
                    self.veo_service, 
                    self.audio_service, 
                    user,
                    original_prompt=state.get("original_prompt"),
                    generation_model=request.generation_model
                )
                generation_tool = gen_tool_wrapper.get_tool()
                
                from src.agents.adk.manager import create_creative_director
                director = create_creative_director(self.enforcer, generation_tool, validator)
                
                await self.session_service.create_session(
                    app_name="adk",
                    user_id=user.email,
                    session_id=session_id,
                    state=state
                )
                
                director_runner = Runner(
                    agent=director,
                    app_name="adk",
                    session_service=self.session_service
                )
                
                user_intent = (
                    f"User ID: {user.email}\n"
                    f"Workspace ID: {request.workspace_id}\n"
                    f"Request: Generate {request.media_type} with prompt: '{request.prompt}'.\n"
                    f"Config: {state.get('request_config')}\n"
                    f"Ref Images: {state.get('reference_image_uris')}\n\n"
                    "Please proceed with the Enforce -> Generate -> Validate workflow."
                )
                
                director_msg = types.Content(role="user", parts=[types.Part(text=user_intent)])
                
                # Copy of the polling loop logic
                def get_long_running_function_call(event: Event) -> types.FunctionCall:
                    if not event.long_running_tool_ids or not event.content or not event.content.parts:
                        return None
                    for part in event.content.parts:
                        if (
                            part
                            and part.function_call
                            and event.long_running_tool_ids
                            and part.function_call.id in event.long_running_tool_ids
                        ):
                            return part.function_call
                    return None

                def get_function_response(event: Event, function_call_id: str) -> types.FunctionResponse:
                    if not event.content or not event.content.parts:
                        return None
                    for part in event.content.parts:
                        if (
                            part
                            and part.function_response
                            and part.function_response.id == function_call_id
                        ):
                            return part.function_response
                    return None

                events_async = director_runner.run_async(user_id=user.email, session_id=session_id, new_message=director_msg)
                
                long_running_function_call = None
                long_running_function_response = None
                current_job_id = None
                
                try:
                    async for event in events_async:
                        logger.info(f"[Director Event] {event.author}: {event}")

                        if event.author == "BrandingEnforcer" and event.content:
                             for part in event.content.parts:
                                 if part.text:
                                      logger.info(f"Values from Enforcer: {part.text}")
                        if not long_running_function_call:
                            long_running_function_call = get_long_running_function_call(event)
                        else:
                            _potential_response = get_function_response(event, long_running_function_call.id)
                            if _potential_response:
                                long_running_function_response = _potential_response
                                if 'job_id' in long_running_function_response.response:
                                    current_job_id = long_running_function_response.response['job_id']
                                    # Publish event when Job ID is captured
                                    await self.event_bus.publish(
                                        f"user_{user.email}",
                                        Event(
                                            author="System",
                                            content=types.Content(
                                                parts=[types.Part(text=f"Captured Long Running Job ID: {current_job_id}")]
                                            )
                                        )
                                    )
                        
                        if event.content and event.content.parts:
                            text = event.content.parts[0].text
                            if text:
                                await self.event_bus.publish(f"user_{user.email}", event)
                except Exception as e:
                    logger.error(f"Error in Director loop: {e}", exc_info=True)
                    await self.event_bus.publish(
                        f"user_{user.email}",
                        Event(
                            author="System",
                            content=types.Content(
                                parts=[types.Part(text=f"Agent Process Failed: {str(e)}")]
                            )
                        )
                    )
                    return

                
                if long_running_function_call and current_job_id:
                    logger.info(f"Director Paused. Polling for Job {current_job_id}...")
                    
                    # Poll loop (Wait for completion)
                    final_job_status = "failed"
                    # Use the fresh repo for polling
                    
                    for _ in range(60): 
                        await asyncio.sleep(2)
                        job = await media_repo.get_by_id(current_job_id)
                        if job:
                            if job.status == JobStatusEnum.COMPLETED:
                                final_job_status = "completed"
                                break
                            if job.status == JobStatusEnum.FAILED:
                                final_job_status = "failed"
                                break
                    
                    logger.info(f"Job finished: {final_job_status}. Resuming...")
                    
                    updated_response = long_running_function_response.model_copy(deep=True)
                    updated_response.response = {
                        "status": final_job_status, 
                        "job_id": current_job_id,
                        "message": "Generation completed."
                    }
                    
                    resume_msg = types.Content(parts=[types.Part(function_response=updated_response)], role='user')
                    
                    async for event in director_runner.run_async(user_id=user.email, session_id=session_id, new_message=resume_msg):
                        logger.info(f"[Director Resumed Event] {event.author}: {event}")
                        if event.content:
                             await self.event_bus.publish(f"user_{user.email}", event)

            except Exception as e:
                logger.error(f"Background ADK Flow Failed: {e}", exc_info=True)
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
