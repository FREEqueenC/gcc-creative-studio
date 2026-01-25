import datetime
from typing import Optional
from fastapi import Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.config.config_service import config_service
from src.credits.credit_model import UserWallet, OrganizationWallet, CreditLog, PriceCatalog
from src.credits.dto.assign_credits_dto import AssignCreditsDto
from src.users.user_model import UserModel

class CreditsService:
    def __init__(self, db: AsyncSession = Depends(get_db)):
        self.db = db

    async def assign_credits(self, dto: AssignCreditsDto, performed_by: UserModel):
        """
        Assigns credits to a user or organization wallet.
        Resets cumulative_spend to 0.
        """
        # Calculate expiration
        if dto.custom_expiration_date:
            expires_at = dto.custom_expiration_date
        else:
            expires_at = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=config_service.DEFAULT_CREDIT_EXPIRATION_DAYS)

        # Ensure timezone awareness
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=datetime.timezone.utc)

        target_wallet = None
        
        if dto.target_user_id:
            stmt = select(UserWallet).where(UserWallet.user_id == dto.target_user_id)
            result = await self.db.execute(stmt)
            target_wallet = result.scalar_one_or_none()
            
            if not target_wallet:
                # Create if missing (should exist from onboarding, but safe fallback)
                target_wallet = UserWallet(user_id=dto.target_user_id, balance=0.0)
                self.db.add(target_wallet)

        elif dto.target_org_id:
            stmt = select(OrganizationWallet).where(OrganizationWallet.organization_id == dto.target_org_id)
            result = await self.db.execute(stmt)
            target_wallet = result.scalar_one_or_none()
            
            if not target_wallet:
                target_wallet = OrganizationWallet(organization_id=dto.target_org_id, balance=0.0)
                self.db.add(target_wallet)

        if not target_wallet:
            raise HTTPException(status_code=404, detail="Target wallet not found")

        # Update Wallet
        target_wallet.balance += dto.amount
        target_wallet.expires_at = expires_at
        target_wallet.cumulative_spend = 0  # Reset rule
        
        # Log Transaction
        log = CreditLog(
            action="assign",
            amount=dto.amount,
            performed_by_user_id=performed_by.id,
            target_user_id=dto.target_user_id,
            target_org_id=dto.target_org_id,
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )
        self.db.add(log)
        
        await self.db.commit()
        await self.db.refresh(target_wallet)
        return target_wallet

    async def get_price(self, model_id: str) -> Optional[PriceCatalog]:
        stmt = select(PriceCatalog).where(PriceCatalog.model_id == model_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def check_balance(self, user_id: int, cost: float, org_id: Optional[int] = None) -> bool:
        """
        Checks if the user or their organizations have enough balance.
        Waterfall logic: User Wallet -> Org Wallet.
        """
        now = datetime.datetime.now(datetime.timezone.utc)

        # 1. Check User Wallet
        stmt = select(UserWallet).where(UserWallet.user_id == user_id)
        result = await self.db.execute(stmt)
        user_wallet = result.scalar_one_or_none()
        
        if user_wallet and user_wallet.balance >= cost:
            if not user_wallet.expires_at or user_wallet.expires_at > now:
                return True
        
        # 2. Check Org Wallet (if provided)
        if org_id:
            stmt = select(OrganizationWallet).where(OrganizationWallet.organization_id == org_id)
            result = await self.db.execute(stmt)
            org_wallet = result.scalar_one_or_none()
            
            if org_wallet and org_wallet.balance >= cost:
                if not org_wallet.expires_at or org_wallet.expires_at > now:
                    return True
        
        return False

    async def deduct_credits(self, user_id: int, cost: float, model_id: str, org_id: Optional[int] = None):
        """
        Deducts credits from User or Org wallet.
        """
        now = datetime.datetime.now(datetime.timezone.utc)
        
        # 1. Try User Wallet
        stmt = select(UserWallet).where(UserWallet.user_id == user_id)
        result = await self.db.execute(stmt)
        user_wallet = result.scalar_one_or_none()
        
        charged_wallet = None
        target_user_id = None
        target_org_id = None

        if user_wallet and user_wallet.balance >= cost:
             if not user_wallet.expires_at or user_wallet.expires_at > now:
                user_wallet.balance -= cost
                user_wallet.cumulative_spend += cost
                charged_wallet = user_wallet
                target_user_id = user_id

        # 2. Try Org Wallet (if not charged user)
        if not charged_wallet:
            # If org_id is provided, check that specific org
            if org_id:
                stmt = select(OrganizationWallet).where(OrganizationWallet.organization_id == org_id)
                result = await self.db.execute(stmt)
                org_wallet = result.scalar_one_or_none()
                
                if org_wallet and org_wallet.balance >= cost:
                     if not org_wallet.expires_at or org_wallet.expires_at > now:
                        org_wallet.balance -= cost
                        org_wallet.cumulative_spend += cost
                        charged_wallet = org_wallet
                        target_org_id = org_id
            else:
                # If no org_id provided, we might need to find one.
                # But for safety, if we can't determine org, we fail or just log negative on user if AUDIT.
                pass

        # 3. Mode Check (Audit vs Enforced)
        if not charged_wallet:
            if config_service.CREDIT_SYSTEM_MODE == "ENFORCED":
                raise HTTPException(status_code=402, detail="Insufficient credits")
            else:
                # AUDIT Mode: Charge User Wallet (go negative)
                if not user_wallet:
                     # Should exist, but if not create it
                     user_wallet = UserWallet(user_id=user_id, balance=0.0)
                     self.db.add(user_wallet)
                
                user_wallet.balance -= cost
                user_wallet.cumulative_spend += cost
                charged_wallet = user_wallet
                target_user_id = user_id

        # Log
        log = CreditLog(
            action="spend",
            amount=-cost,
            performed_by_user_id=user_id,
            target_user_id=target_user_id,
            target_org_id=target_org_id,
            model_id=model_id,
            timestamp=now
        )
        self.db.add(log)
        await self.db.commit()
