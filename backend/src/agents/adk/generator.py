import logging
from typing import AsyncGenerator, Dict, Any

from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event, EventActions
from google.genai import types

from src.images.dto.create_imagen_dto import CreateImagenDto
from src.videos.dto.create_veo_dto import CreateVeoDto
from src.audios.dto.create_audio_dto import CreateAudioDto
from src.common.base_dto import GenerationModelEnum, AspectRatioEnum
from src.images.imagen_service import ImagenService
from src.videos.veo_service import VeoService
from src.audios.audio_service import AudioService
from src.users.user_model import UserModel

logger = logging.getLogger(__name__)

from pydantic import PrivateAttr

class MediaGeneratorADK(BaseAgent):
    """
    Custom Agent that wraps backend generation services (Imagen, Veo, Audio).
    It is deterministic and orchestrates the service calls based on session state.
    """
    _imagen_service: Any = PrivateAttr()
    _veo_service: Any = PrivateAttr()
    _audio_service: Any = PrivateAttr()

    def __init__(
        self,
        name: str,
        imagen_service: ImagenService,
        veo_service: VeoService,
        audio_service: AudioService,
    ):
        super().__init__(name=name)
        self._imagen_service = imagen_service
        self._veo_service = veo_service
        self._audio_service = audio_service
    
    @property
    def imagen_service(self):
        return self._imagen_service

    @property
    def veo_service(self):
        return self._veo_service

    @property
    def audio_service(self):
        return self._audio_service

    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        """
        Reads configuration from state, executes generation, and updates state.
        """
        state = ctx.session.state
        
        # 1. Retrieve Context
        # We expect these to be populated in the session state by the caller (AgentService)
        # or previous agents.
        prompt = state.get("enhanced_prompt") or state.get("original_prompt")
        media_type = state.get("media_type", "IMAGE")
        workspace_id = state.get("workspace_id")
        user: UserModel = state.get("current_user") # Passed as object or handled via ID? 
        # Note: Passing complex objects in state is fine in-memory.
        
        if not prompt:
            yield Event(author=self.name, content=types.Content(parts=[types.Part(text="Error: No prompt found in state.")]))
            return

        request_config = state.get("request_config", {}) # Dict of other params
        generation_model = request_config.get("generation_model")
        
        logger.info(f"[{self.name}] Starting generation. Type: {media_type}, Model: {generation_model}, Prompt: {prompt}")
        
        # 2. Dispatch
        media_response = None
        
        try:
            from concurrent.futures import ThreadPoolExecutor
            # TODO: Inject executor or use global one
            executor = ThreadPoolExecutor(max_workers=1)

            if media_type == "IMAGE":
                # Prepare DTO
                dto = CreateImagenDto(
                    prompt=prompt,
                    workspace_id=workspace_id,
                    generation_model=generation_model or GenerationModelEnum.GEMINI_2_5_FLASH_IMAGE_PREVIEW,
                    aspect_ratio=request_config.get("aspect_ratio") or AspectRatioEnum.RATIO_1_1,
                    number_of_media=request_config.get("number_of_media", 1),
                    style=request_config.get("style"),
                    reference_image_gcs_uris=state.get("reference_image_uris") # From Enforcer/Tool
                )
                media_response = await self.imagen_service.start_image_generation_job(
                    request_dto=dto, user=user, executor=executor
                )
                
            elif media_type == "VIDEO":
                dto = CreateVeoDto(
                    prompt=prompt,
                    workspace_id=workspace_id,
                    generation_model=generation_model or GenerationModelEnum.VEO_2_0_001,
                    aspect_ratio=request_config.get("aspect_ratio") or AspectRatioEnum.RATIO_16_9,
                    duration_seconds=request_config.get("duration_seconds", 5),
                    generate_audio=request_config.get("generate_audio", False),
                    style=request_config.get("style")
                )
                media_response = await self.veo_service.start_video_generation_job(
                    request_dto=dto, user=user, executor=executor
                )
                
            elif media_type == "AUDIO":
                from src.audios.audio_constants import VoiceEnum, LanguageEnum
                dto = CreateAudioDto(
                    prompt=prompt,
                    workspace_id=workspace_id,
                    model=generation_model or GenerationModelEnum.GEMINI_2_5_FLASH_TTS,
                    voice_name=request_config.get("voice_name") or VoiceEnum.PUCK,
                    language_code=LanguageEnum.EN_US,
                    sample_count=request_config.get("number_of_media", 1)
                )
                media_response = await self.audio_service.generate_audio(
                    request_dto=dto, user=user
                )
                
            else:
                yield Event(author=self.name, content=types.Content(parts=[types.Part(text=f"Unsupported media type: {media_type}")]))
                return

            # 3. Update State
            if media_response:
                state["generated_assets"] = [{
                    "id": media_response.id,
                    "status": media_response.status,
                    "gcs_uris": media_response.gcs_uris if hasattr(media_response, 'gcs_uris') else []
                }]
                state["job_id"] = media_response.id
                
                yield Event(
                    author=self.name, 
                    content=types.Content(parts=[types.Part(text=f"Generation started. Job ID: {media_response.id}")])
                )
            else:
                yield Event(author=self.name, content=types.Content(parts=[types.Part(text="Generation failed to return a response.")]))

        except Exception as e:
            logger.error(f"Generation failed: {e}")
            yield Event(author=self.name, content=types.Content(parts=[types.Part(text=f"Generation Error: {str(e)}")]))
