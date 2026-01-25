import asyncio
import logging
import sys
import os

# Add the backend directory to sys.path to allow imports
sys.path.append(os.path.join(os.path.dirname(__file__), "../.."))

from sqlalchemy import select
from src.database import get_db, AsyncSessionLocal
from src.credits.credit_model import PriceCatalog, BudgetDeposit

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

INITIAL_PRICES = [
    {"model_id": "gemini-1.5-pro-002", "category": "Google", "cost": 10.0},
    {"model_id": "gemini-1.5-flash-002", "category": "Google", "cost": 1.0},
    {"model_id": "imagen-3.0-generate-001", "category": "Google", "cost": 8.0},
    {"model_id": "veo-2.0-generate-001", "category": "Youtube", "cost": 50.0},
    {"model_id": "virtual-try-on-preview-08-04", "category": "Google", "cost": 15.0},
]

INITIAL_BUDGET = 70000.0

async def seed_credits():
    logger.info("Starting Credit Economy Seeding...")
    
    async with AsyncSessionLocal() as session:
        # 1. Seed Price Catalog
        for price_data in INITIAL_PRICES:
            stmt = select(PriceCatalog).where(PriceCatalog.model_id == price_data["model_id"])
            result = await session.execute(stmt)
            existing_price = result.scalar_one_or_none()
            
            if existing_price:
                existing_price.category = price_data["category"]
                existing_price.cost = price_data["cost"]
                logger.info(f"Updated price for {price_data['model_id']}")
            else:
                new_price = PriceCatalog(**price_data)
                session.add(new_price)
                logger.info(f"Created price for {price_data['model_id']}")
        
        # 2. Seed Initial Budget (only if no deposits exist)
        stmt = select(BudgetDeposit)
        result = await session.execute(stmt)
        existing_deposit = result.first()
        
        if not existing_deposit:
            deposit = BudgetDeposit(
                amount_usd=INITIAL_BUDGET,
                notes="Initial Grant"
            )
            session.add(deposit)
            logger.info(f"Deposited initial budget of ${INITIAL_BUDGET}")
        else:
            logger.info("Budget deposits already exist, skipping initial grant.")
            
        await session.commit()
        logger.info("Seeding complete.")

if __name__ == "__main__":
    asyncio.run(seed_credits())
