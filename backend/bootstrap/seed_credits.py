import asyncio
import logging
import sys
import os
from typing import List
from pydantic import BaseModel
from decimal import Decimal

# Add the backend directory to sys.path to allow imports
sys.path.append(os.path.join(os.path.dirname(__file__), "../.."))

from sqlalchemy import select
from src.database import AsyncSessionLocal
from src.credits.credit_model import PriceCatalog, BudgetDeposit
from src.common.base_dto import GenerationModelEnum
from src.credits.dto.price_catalog_dto import ModelCategoryEnum
from src.users.user_model import User
from src.organizations.organization_model import Organization
from src.workspaces.schema.workspace_model import Workspace

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PriceCatalogItem(BaseModel):
    model_id: GenerationModelEnum
    category: ModelCategoryEnum
    cost: Decimal

# Prices are based on USD, conceptually 1 USD = 100 Credits.
# Ref: https://cloud.google.com/vertex-ai/generative-ai/pricing
INITIAL_PRICES: List[PriceCatalogItem] = [
    # Image Models
    PriceCatalogItem(model_id=GenerationModelEnum.IMAGEN_3_001, category=ModelCategoryEnum.IMAGE, cost=Decimal("0.020")), # Per image
    PriceCatalogItem(model_id=GenerationModelEnum.IMAGEN_3_FAST, category=ModelCategoryEnum.IMAGE, cost=Decimal("0.006")), # Per image
    PriceCatalogItem(model_id=GenerationModelEnum.IMAGEGEN_006, category=ModelCategoryEnum.IMAGE, cost=Decimal("0.020")), # Per image
    PriceCatalogItem(model_id=GenerationModelEnum.IMAGEGEN_005, category=ModelCategoryEnum.IMAGE, cost=Decimal("0.010")), # Per image
    PriceCatalogItem(model_id=GenerationModelEnum.IMAGEGEN_002, category=ModelCategoryEnum.IMAGE, cost=Decimal("0.005")), # Per image
    PriceCatalogItem(model_id=GenerationModelEnum.GEMINI_3_PRO_IMAGE_PREVIEW, category=ModelCategoryEnum.IMAGE, cost=Decimal("0.010")), # Placeholder
    # VTO
    PriceCatalogItem(model_id=GenerationModelEnum.VTO, category=ModelCategoryEnum.VTO, cost=Decimal("0.150")), # Placeholder per generation

    # Video Models (Cost per second)
    PriceCatalogItem(model_id=GenerationModelEnum.VEO_2_FAST, category=ModelCategoryEnum.VIDEO, cost=Decimal("0.014")), # Per second
    PriceCatalogItem(model_id=GenerationModelEnum.VEO_2_QUALITY, category=ModelCategoryEnum.VIDEO, cost=Decimal("0.021")), # Per second

    # Audio Models
    PriceCatalogItem(model_id=GenerationModelEnum.LYRIA_002, category=ModelCategoryEnum.AUDIO, cost=Decimal("0.005")), # Placeholder per second/token
    PriceCatalogItem(model_id=GenerationModelEnum.CHIRP_3, category=ModelCategoryEnum.AUDIO, cost=Decimal("0.002")), # Placeholder
    PriceCatalogItem(model_id=GenerationModelEnum.GEMINI_2_5_FLASH_TTS, category=ModelCategoryEnum.AUDIO, cost=Decimal("0.001")), # Placeholder per char

    # Others from Enum (with placeholder costs and categories)
    PriceCatalogItem(model_id=GenerationModelEnum.IMAGEN_4_001, category=ModelCategoryEnum.IMAGE, cost=Decimal("0.025")), 
    PriceCatalogItem(model_id=GenerationModelEnum.IMAGEN_4_ULTRA, category=ModelCategoryEnum.IMAGE, cost=Decimal("0.050")), 
    PriceCatalogItem(model_id=GenerationModelEnum.IMAGEN_4_ULTRA_PREVIEW, category=ModelCategoryEnum.IMAGE, cost=Decimal("0.040")), 
    PriceCatalogItem(model_id=GenerationModelEnum.IMAGEN_4_FAST, category=ModelCategoryEnum.IMAGE, cost=Decimal("0.010")), 
    PriceCatalogItem(model_id=GenerationModelEnum.IMAGEN_4_FAST_PREVIEW, category=ModelCategoryEnum.IMAGE, cost=Decimal("0.008")), 
    PriceCatalogItem(model_id=GenerationModelEnum.IMAGEN_3_002, category=ModelCategoryEnum.IMAGE, cost=Decimal("0.020")), 
    PriceCatalogItem(model_id=GenerationModelEnum.GEMINI_2_5_PRO, category=ModelCategoryEnum.TEXT, cost=Decimal("0.0005")), # Per 1k chars input
    PriceCatalogItem(model_id=GenerationModelEnum.GEMINI_2_5_PRO, category=ModelCategoryEnum.IMAGE, cost=Decimal("0.0025")), # Per image input
    PriceCatalogItem(model_id=GenerationModelEnum.GEMINI_2_5_FLASH, category=ModelCategoryEnum.TEXT, cost=Decimal("0.0000625")),# Per 1k chars input
    PriceCatalogItem(model_id=GenerationModelEnum.GEMINI_2_5_FLASH, category=ModelCategoryEnum.IMAGE, cost=Decimal("0.00125")), # Per image input
    PriceCatalogItem(model_id=GenerationModelEnum.GEMINI_3_PRO_PREVIEW, category=ModelCategoryEnum.TEXT, cost=Decimal("0.0005")), 
    PriceCatalogItem(model_id=GenerationModelEnum.GEMINI_3_FLASH_PREVIEW, category=ModelCategoryEnum.TEXT, cost=Decimal("0.0000625")), 
    PriceCatalogItem(model_id=GenerationModelEnum.VEO_3_1_PREVIEW, category=ModelCategoryEnum.VIDEO, cost=Decimal("0.025")), 
    PriceCatalogItem(model_id=GenerationModelEnum.VEO_3_FAST, category=ModelCategoryEnum.VIDEO, cost=Decimal("0.018")), 
    PriceCatalogItem(model_id=GenerationModelEnum.VEO_3_QUALITY, category=ModelCategoryEnum.VIDEO, cost=Decimal("0.028")), 
    PriceCatalogItem(model_id=GenerationModelEnum.VEO_3_FAST_PREVIEW, category=ModelCategoryEnum.VIDEO, cost=Decimal("0.016")), 
    PriceCatalogItem(model_id=GenerationModelEnum.VEO_3_QUALITY_PREVIEW, category=ModelCategoryEnum.VIDEO, cost=Decimal("0.026")), 
    PriceCatalogItem(model_id=GenerationModelEnum.VEO_2_GENERATE_EXP, category=ModelCategoryEnum.VIDEO, cost=Decimal("0.030")), 
    PriceCatalogItem(model_id=GenerationModelEnum.GEMINI_2_5_FLASH_LITE_PREVIEW_TTS, category=ModelCategoryEnum.AUDIO, cost=Decimal("0.0005")), 
    PriceCatalogItem(model_id=GenerationModelEnum.GEMINI_2_5_PRO_TTS, category=ModelCategoryEnum.AUDIO, cost=Decimal("0.0015")), 
]

# INITIAL_BUDGET = Decimal("70000.0")

async def main(db=None):
    logger.info("Starting Credit Economy Seeding...")
    
    if db is None:
        async with AsyncSessionLocal() as session:
            await _seed_credits_logic(session)
    else:
        await _seed_credits_logic(db)

async def _seed_credits_logic(session):
    # 1. Seed Price Catalog
    for price_item in INITIAL_PRICES:
        stmt = select(PriceCatalog).where(
            PriceCatalog.model_id == price_item.model_id.value,
            PriceCatalog.category == price_item.category
        )
        result = await session.execute(stmt)
        existing_price = result.scalar_one_or_none()
        
        if existing_price:
            existing_price.cost = price_item.cost
            logger.info(f"Updated price for {price_item.model_id.value} ({price_item.category.value})")
        else:
            new_price = PriceCatalog(
                model_id=price_item.model_id.value,
                category=price_item.category,
                cost=price_item.cost
            )
            session.add(new_price)
            logger.info(f"Created price for {price_item.model_id.value} ({price_item.category.value})")
    
    # 2. Seed Initial Budget (only if no deposits exist)
    # stmt = select(BudgetDeposit)
    # result = await session.execute(stmt)
    # existing_deposit = result.first()
    
    # if not existing_deposit:
    #     deposit = BudgetDeposit(
    #         amount_usd=INITIAL_BUDGET,
    #         notes="Initial Grant"
    #     )
    #     session.add(deposit)
    #     logger.info(f"Deposited initial budget of ${INITIAL_BUDGET}")
    # else:
    #     logger.info("Budget deposits already exist, skipping initial grant.")
        
    await session.commit()
    logger.info("Seeding complete.")

if __name__ == "__main__":
    asyncio.run(main())
