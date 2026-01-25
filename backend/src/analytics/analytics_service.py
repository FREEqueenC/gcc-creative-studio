from typing import List, Dict, Any
from fastapi import Depends
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.credits.credit_model import CreditLog, PriceCatalog, BudgetDeposit, UserWallet
from src.users.user_model import User

class AnalyticsService:
    def __init__(self, db: AsyncSession = Depends(get_db)):
        self.db = db

    async def get_token_usage(self) -> List[Dict[str, Any]]:
        """
        Returns daily spend grouped by category.
        """
        # Join CreditLog and PriceCatalog on model_id
        # Group by Date and Category
        stmt = (
            select(
                func.date(CreditLog.timestamp).label("date"),
                PriceCatalog.category,
                func.sum(func.abs(CreditLog.amount)).label("spend")
            )
            .join(PriceCatalog, CreditLog.model_id == PriceCatalog.model_id)
            .where(CreditLog.action == "spend")
            .group_by(func.date(CreditLog.timestamp), PriceCatalog.category)
            .order_by("date")
        )
        
        result = await self.db.execute(stmt)
        rows = result.all()
        
        # Format for frontend (e.g. list of {date: '...', category: '...', spend: ...})
        return [
            {"date": row.date, "category": row.category, "spend": float(row.spend)}
            for row in rows
        ]

    async def get_token_budgets(self) -> Dict[str, Any]:
        """
        Returns total budget, total spend, and spend by category.
        """
        # 1. Total Budget
        stmt_budget = select(func.sum(BudgetDeposit.amount_usd))
        result_budget = await self.db.execute(stmt_budget)
        total_budget = result_budget.scalar() or 0.0

        # 2. Total Spend
        stmt_spend = select(func.sum(func.abs(CreditLog.amount))).where(CreditLog.action == "spend")
        result_spend = await self.db.execute(stmt_spend)
        total_spend = result_spend.scalar() or 0.0

        # 3. Spend by Category
        stmt_category = (
            select(
                PriceCatalog.category,
                func.sum(func.abs(CreditLog.amount)).label("spend")
            )
            .join(PriceCatalog, CreditLog.model_id == PriceCatalog.model_id)
            .where(CreditLog.action == "spend")
            .group_by(PriceCatalog.category)
        )
        result_category = await self.db.execute(stmt_category)
        category_spend = [
            {"category": row.category, "spend": float(row.spend)}
            for row in result_category.all()
        ]

        return {
            "total_budget": float(total_budget),
            "total_spend": float(total_spend),
            "category_spend": category_spend
        }

    async def get_active_roles(self) -> List[Dict[str, Any]]:
        """
        Returns breakdown of user roles.
        Using unnest(roles) as requested.
        """
        stmt = (
            select(
                func.unnest(User.roles).label("role"),
                func.count(User.id).label("count")
            )
            .group_by("role")
        )
        result = await self.db.execute(stmt)
        return [
            {"role": row.role, "count": row.count}
            for row in result.all()
        ]

    async def get_organization_usage(self, org_id: int) -> List[Dict[str, Any]]:
        """
        Returns daily spend for a specific organization.
        """
        stmt = (
            select(
                func.date(CreditLog.timestamp).label("date"),
                PriceCatalog.category,
                func.sum(func.abs(CreditLog.amount)).label("spend")
            )
            .join(PriceCatalog, CreditLog.model_id == PriceCatalog.model_id)
            .where(CreditLog.action == "spend")
            .where(CreditLog.target_org_id == org_id)
            .group_by(func.date(CreditLog.timestamp), PriceCatalog.category)
            .order_by("date")
        )
        
        result = await self.db.execute(stmt)
        rows = result.all()
        
        return [
            {"date": row.date, "category": row.category, "spend": float(row.spend)}
            for row in rows
        ]

    async def get_user_usage(self, user_id: int) -> List[Dict[str, Any]]:
        """
        Returns daily spend for a specific user.
        """
        stmt = (
            select(
                func.date(CreditLog.timestamp).label("date"),
                PriceCatalog.category,
                func.sum(func.abs(CreditLog.amount)).label("spend")
            )
            .join(PriceCatalog, CreditLog.model_id == PriceCatalog.model_id)
            .where(CreditLog.action == "spend")
            .where(CreditLog.target_user_id == user_id)
            .group_by(func.date(CreditLog.timestamp), PriceCatalog.category)
            .order_by("date")
        )
        
        result = await self.db.execute(stmt)
        rows = result.all()
        
        return [
            {"date": row.date, "category": row.category, "spend": float(row.spend)}
            for row in rows
        ]
