from typing import Annotated, Optional, List, Dict, Any

from fastapi import Query
from pydantic import Field, field_validator
from enum import Enum

from src.common.base_dto import (
    BaseDto,
    AspectRatioEnum,
    GenerationModelEnum,
    StyleEnum,
)
from src.audios.audio_constants import VoiceEnum

class MediaTypeEnum(str, Enum):
    IMAGE = "IMAGE"
    VIDEO = "VIDEO"
    AUDIO = "AUDIO"

class AgentGenerationRequest(BaseDto):
    """
    Unified request DTO for the Agentic RAG flow.
    Harmonizes fields across Image, Video, and Audio generation.
    """
    prompt: Annotated[str, Query(max_length=10000)] = Field(
        description="The prompt to generative media for."
    )
    workspace_id: int = Field(
        ge=1, description="The ID of the workspace for this generation."
    )
    media_type: MediaTypeEnum = Field(
        default=MediaTypeEnum.IMAGE,
        description="The target media type to generate."
    )
    generation_model: Optional[GenerationModelEnum] = Field(
        default=None,
        description="Specific model to use. If None, the agent selects the best model."
    )
    
    # Common / Shared Options
    aspect_ratio: Optional[AspectRatioEnum] = Field(
        default=None,
        description="Aspect ratio for Image/Video generation."
    )
    number_of_media: int = Field(
        default=1,
        ge=1,
        le=4,
        description="Number of variations to generate.",
    )
    style: Optional[StyleEnum] = Field(
        default=None,
        description="Visual style for Images/Video."
    )
    
    # Video Specific
    duration_seconds: Optional[int] = Field(
        default=5,
        ge=1,
        le=8,
        description="[Video Only] Duration in seconds."
    )
    generate_audio: bool = Field(
        default=False,
        description="[Video Only] Whether to generate audio for the video."
    )
    
    # Audio Specific
    voice_name: Optional[VoiceEnum] = Field(
        default=VoiceEnum.PUCK,
        description="[Audio Only] Voice to use for TTS."
    )
    
    # Multimodal / RAG
    reference_image_uri: Optional[str] = Field(
        default=None,
        description="Optional GCS URI for a reference image."
    )

class AgentGenerationResponse(BaseDto):
    original_prompt: str
    enhanced_prompt: str
    generated_assets: List[Dict[str, Any]] # Contains uri, validation_status, reasoning
    session_id: str
