from .base_strategy import CostCalculationStrategy
from src.common.base_dto import BaseDto
from src.images.dto.create_imagen_dto import CreateImagenDto

class ImageCostStrategy(CostCalculationStrategy):
    async def calculate(self, dto: BaseDto) -> float:
        if not isinstance(dto, CreateImagenDto):
            return 0.0
        
        model_id = getattr(dto, 'generation_model', getattr(dto, 'model', 'unknown'))
        base_price = await self.get_base_price(str(model_id))
        
        multiplier = dto.number_of_media
        return base_price * multiplier
