from abc import ABC, abstractmethod
from src.common.base_dto import BaseDto
from src.credits.credit_model import PriceCatalog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import logging
from src.credits.dto.price_catalog_dto import ModelCategoryEnum

class CostCalculationStrategy(ABC):
    def __init__(self, db: AsyncSession):
        self.db = db

    @abstractmethod
    async def calculate(self, dto: BaseDto) -> float:
        pass

    async def get_base_price(self, model_id: str, category: ModelCategoryEnum) -> float:
        if not model_id or model_id == 'unknown':
            return 0.0
        
        stmt = select(PriceCatalog).where(
            PriceCatalog.model_id == model_id,
            PriceCatalog.category == category
        )
        result = await self.db.execute(stmt)
        price_entry = result.scalar_one_or_none()

        if not price_entry:
            logging.warning(f"Price catalog entry not found for model_id: {model_id} and category: {category.value}")
            return 0.0
            
        return price_entry.cost
