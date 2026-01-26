from .base_strategy import CostCalculationStrategy
from src.common.base_dto import BaseDto
from src.videos.dto.create_veo_dto import CreateVeoDto
from src.credits.dto.price_catalog_dto import ModelCategoryEnum
from decimal import Decimal

class VideoCostStrategy(CostCalculationStrategy):
    async def calculate(self, dto: BaseDto) -> float:
        if not isinstance(dto, CreateVeoDto):
            return 0.0
        
        model_id = getattr(dto, 'generation_model', getattr(dto, 'model', 'unknown'))
        base_price = await self.get_base_price(model_id.value, ModelCategoryEnum.VIDEO)
        
        # TODO: Implement actual video cost logic based on duration, quality, etc.
        multiplier = 1.0 
        return base_price * Decimal(multiplier)
