import logging
import asyncio
from typing import Any, Dict, Optional
from google.adk.tools import LongRunningFunctionTool
from src.images.dto.create_imagen_dto import CreateImagenDto, AspectRatioEnum
from src.videos.dto.create_veo_dto import CreateVeoDto
from src.audios.dto.create_audio_dto import CreateAudioDto
from src.common.base_dto import GenerationModelEnum
from src.users.user_model import UserModel

logger = logging.getLogger(__name__)

class MediaGenerationToolWrapper:
    def __init__(self, imagen_service, veo_service, audio_service, user: UserModel, original_prompt: Optional[str] = None, generation_model: Optional[GenerationModelEnum] = None):
        self.imagen_service = imagen_service
        self.veo_service = veo_service
        self.audio_service = audio_service
        self.user = user
        self.original_prompt = original_prompt
        self.generation_model = generation_model
        
    def get_tool(self) -> LongRunningFunctionTool:
        return LongRunningFunctionTool(func=self.start_generation)

    async def start_generation(
        self,
        prompt: str,
        media_type: str,
        workspace_id: str,
        user_email: str,
        # Optional args
        number_of_media: int = 1,
        aspect_ratio: str = "1:1",
        style: Optional[str] = None,
        reference_image_uris: Optional[str] = None, # Passed as comma string or list? Tool usually string or simple types.
        # Actually proper typing for list in Tool? Defaults to string in JSON usually? 
        # Let's assume list but handle string split if needed.
        # But for valid JSON tool call it can be list.
    ) -> Dict[str, Any]:
        """
        Starts a media generation job.
        Returns a dictionary containing the Job ID and initial status.
        The system will pause and wait for this job to complete.
        """
        logger.info(f"Tool invoked: start_generation for {media_type}")
        
        # Use the bound user object which has the correct ID
        user = self.user
        
        # We need to dispatch based on media_type
        # Executor is needed for sync parts of services?
        from concurrent.futures import ThreadPoolExecutor
        executor = ThreadPoolExecutor(max_workers=1)
        
        media_response = None
        
        # Normalize ref images
        ref_images = []
        if reference_image_uris:
            if isinstance(reference_image_uris, list):
                ref_images = reference_image_uris
            elif isinstance(reference_image_uris, str):
                ref_images = [u.strip() for u in reference_image_uris.split(",") if u.strip()]

        if media_type.upper() == "IMAGE":
            model_to_use = self.generation_model or GenerationModelEnum.GEMINI_2_5_FLASH_IMAGE_PREVIEW
            dto = CreateImagenDto(
                prompt=prompt,
                workspace_id=int(workspace_id),
                generation_model=model_to_use,
                aspect_ratio=AspectRatioEnum(aspect_ratio) if aspect_ratio else AspectRatioEnum.RATIO_1_1,
                number_of_media=number_of_media,
                style=style,
                reference_image_gcs_uris=ref_images
            )
            media_response = await self.imagen_service.start_image_generation_job(
                request_dto=dto, 
                user=user, 
                executor=executor
            )
            
        elif media_type.upper() == "VIDEO":
            dto = CreateVeoDto(
                prompt=prompt,
                workspace_id=int(workspace_id),
                generation_model=GenerationModelEnum.VEO_2_0_001,
                aspect_ratio=AspectRatioEnum(aspect_ratio) if aspect_ratio else AspectRatioEnum.RATIO_16_9,
                duration_seconds=5,
                style=style
            )
            media_response = await self.veo_service.start_video_generation_job(
                request_dto=dto, 
                user=user, 
                executor=executor
            )
            
        # ... Audio ...
        
        if media_response:
            # Update lineage if original_prompt is available and different
            if self.original_prompt and self.original_prompt != prompt:
                try:
                    repo = None
                    if media_type.upper() == "IMAGE":
                        repo = self.imagen_service.media_repo
                    elif media_type.upper() == "VIDEO":
                        repo = self.veo_service.media_repo
                    
                    if repo:
                        await repo.update(media_response.id, {
                            "original_prompt": self.original_prompt,
                            "rewritten_prompt": prompt
                        })
                        logger.info(f"Updated prompt lineage for MediaItem {media_response.id}")
                except Exception as e:
                    logger.error(f"Failed to update prompt lineage: {e}")

            return {
                "job_id": media_response.id,
                "status": "pending",
                "media_type": media_type
            }
        
        return {"error": "Failed to start generation"}
