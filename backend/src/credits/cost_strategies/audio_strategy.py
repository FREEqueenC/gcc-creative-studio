from .base_strategy import CostCalculationStrategy
from src.common.base_dto import BaseDto
from src.audios.dto.create_audio_dto import CreateAudioDto

class AudioCostStrategy(CostCalculationStrategy):
    async def calculate(self, dto: BaseDto) -> float:
        if not isinstance(dto, CreateAudioDto):
            return 0.0
        
        model_id = getattr(dto, 'generation_model', getattr(dto, 'model', 'unknown'))
        base_price = await self.get_base_price(str(model_id))
        
        multiplier = 1.0
        if "lyria" in str(model_id).lower():
            multiplier = dto.sample_count
            
        return base_price * multiplier
