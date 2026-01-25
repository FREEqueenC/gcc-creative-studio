from pydantic import BaseModel
from datetime import datetime
from enum import Enum

class ModelCategoryEnum(str, Enum):
    IMAGE = "Image"
    VIDEO = "Video"
    AUDIO = "Audio"
    VTO = "VTO"
    TEXT = "Text"

class PriceCatalogDto(BaseModel):
    model_id: str
    category: ModelCategoryEnum
    cost: float
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class CreatePriceCatalogDto(BaseModel):
    model_id: str
    category: ModelCategoryEnum
    cost: float

class UpdatePriceCatalogDto(BaseModel):
    category: ModelCategoryEnum | None = None
    cost: float | None = None
