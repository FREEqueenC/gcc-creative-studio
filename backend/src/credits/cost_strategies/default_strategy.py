from .base_strategy import CostCalculationStrategy
from src.common.base_dto import BaseDto

class DefaultCostStrategy(CostCalculationStrategy):
    async def calculate(self, dto: BaseDto) -> float:
        model_id = getattr(dto, 'generation_model', getattr(dto, 'model', 'unknown'))
        return await self.get_base_price(str(model_id))
