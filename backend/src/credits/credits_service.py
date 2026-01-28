import datetime
from typing import Optional, List, Dict, Type, Any
from fastapi import Depends, HTTPException
from sqlalchemy import select, func, cast, Date
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.config.config_service import config_service
from src.credits.credit_model import CreditLog, UserWallet, OrganizationWallet, PriceCatalog
from src.credits.dto.assign_credits_dto import AssignCreditsDto
from src.users.user_model import User
from src.organizations.organization_model import Organization
from src.common.schema.media_item_model import MediaItem
from src.users.user_model import UserModel
from src.common.base_dto import BaseDto
from src.images.dto.create_imagen_dto import CreateImagenDto
from src.audios.dto.create_audio_dto import CreateAudioDto
from src.videos.dto.create_veo_dto import CreateVeoDto
from src.credits.dto.price_catalog_dto import CreatePriceCatalogDto, UpdatePriceCatalogDto, ModelCategoryEnum

from src.credits.cost_strategies import (
    CostCalculationStrategy,
    ImageCostStrategy,
    AudioCostStrategy,
    VideoCostStrategy,
    DefaultCostStrategy,
)

class CreditsService:
    def __init__(self, db: AsyncSession = Depends(get_db)):
        self.db = db
        self.strategies: Dict[Type[BaseDto], CostCalculationStrategy] = {
            CreateImagenDto: ImageCostStrategy(db),
            CreateAudioDto: AudioCostStrategy(db),
            CreateVeoDto: VideoCostStrategy(db),
        }
        self.default_strategy = DefaultCostStrategy(db)

    def _get_strategy(self, dto: BaseDto) -> CostCalculationStrategy:
        dto_type = type(dto)
        return self.strategies.get(dto_type, self.default_strategy)

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
        # target_wallet.cumulative_spend = 0  # Reset rule if we want 'Spend since last top up'
        
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

    async def calculate_cost(self, dto: BaseDto) -> float:
        strategy = self._get_strategy(dto)
        return await strategy.calculate(dto)

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
    async def get_wallet_balance(self, user_id: Optional[int] = None, org_id: Optional[int] = None) -> float:
        if user_id:
            stmt = select(UserWallet).where(UserWallet.user_id == user_id)
            result = await self.db.execute(stmt)
            wallet = result.scalar_one_or_none()
            return wallet.balance if wallet else 0.0
        elif org_id:
            stmt = select(OrganizationWallet).where(OrganizationWallet.organization_id == org_id)
            result = await self.db.execute(stmt)
            wallet = result.scalar_one_or_none()
            return wallet.balance if wallet else 0.0
        return 0.0

    # Price Catalog Methods
    async def get_all_prices(self) -> List[PriceCatalog]:
        stmt = select(PriceCatalog).order_by(PriceCatalog.category, PriceCatalog.model_id)
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def create_price(self, dto: CreatePriceCatalogDto) -> PriceCatalog:
        existing = await self.db.get(PriceCatalog, (dto.model_id, dto.category))
        if existing:
            raise HTTPException(status_code=400, detail=f"Price for model_id '{dto.model_id}' and category '{dto.category}' already exists.")
        new_price = PriceCatalog(**dto.model_dump())
        self.db.add(new_price)
        await self.db.commit()
        await self.db.refresh(new_price)
        return new_price

    async def update_price(self, model_id: str, category: ModelCategoryEnum, dto: UpdatePriceCatalogDto) -> PriceCatalog:
        price_entry = await self.db.get(PriceCatalog, (model_id, category))
        if not price_entry:
            raise HTTPException(status_code=404, detail=f"Price for model_id '{model_id}' and category '{category}' not found.")
        
        update_data = dto.model_dump(exclude_unset=True)
        if 'category' in update_data:
             del update_data['category'] # Category is part of PK, cannot be updated

        for key, value in update_data.items():
            setattr(price_entry, key, value)
            
        await self.db.commit()
        await self.db.refresh(price_entry)
        return price_entry

    async def delete_price(self, model_id: str, category: ModelCategoryEnum) -> None:
        price_entry = await self.db.get(PriceCatalog, (model_id, category))
        if not price_entry:
            raise HTTPException(status_code=404, detail=f"Price for model_id '{model_id}' and category '{category}' not found.")
        
        await self.db.delete(price_entry)
        await self.db.commit()

    # Admin Dashboard Service Methods
    async def get_admin_overview_stats(self, current_user: UserModel) -> Dict[str, Any]:
        if current_user.is_super_admin:
            total_users = await self.db.scalar(select(func.count(User.id)))
            total_organizations = await self.db.scalar(select(func.count(Organization.id)))

            media_counts = await self.db.execute(
                select(
                    MediaItem.type,
                    func.count(MediaItem.id)
                ).group_by(MediaItem.type)
            )
            counts_by_type = {row[0]: row[1] for row in media_counts}

            return {
                "totalUsers": total_users,
                "totalOrganizations": total_organizations,
                "imagesGenerated": counts_by_type.get(ModelCategoryEnum.IMAGE, 0),
                "videosGenerated": counts_by_type.get(ModelCategoryEnum.VIDEO, 0),
                "audiosGenerated": counts_by_type.get(ModelCategoryEnum.AUDIO, 0)
            }
        else:
            # TODO: Implement for Org Admin - scope by organization
            raise HTTPException(status_code=501, detail="Org Admin stats not yet implemented")

    async def get_admin_usage_over_time(self, current_user: UserModel) -> List[Dict[str, Any]]:
        if current_user.is_super_admin:
            # Query to get daily spend grouped by category
            stmt = select(
                cast(CreditLog.timestamp, Date).label("date"),
                PriceCatalog.category,
                func.sum(func.abs(CreditLog.amount)).label("total_spent")
            ).join(
                PriceCatalog, CreditLog.model_id == PriceCatalog.model_id
            ).where(
                CreditLog.action == "spend"
            ).group_by(
                cast(CreditLog.timestamp, Date),
                PriceCatalog.category
            ).order_by(
                cast(CreditLog.timestamp, Date)
            )
            
            result = await self.db.execute(stmt)
            rows = result.fetchall()

            # Pivot data for chart
            data_map: Dict[str, Dict[str, Any]] = {}
            for row in rows:
                date_str = row.date.isoformat()
                category = row.category.name
                spent = float(row.total_spent)

                if date_str not in data_map:
                    data_map[date_str] = {"date": date_str}
                
                data_map[date_str][category] = spent

            # Calculate Totals for each date
            for date_str in data_map:
                total_spent = sum(value for key, value in data_map[date_str].items() if key != 'date')
                data_map[date_str]['Total'] = total_spent

            if not data_map:
                # Mock data if empty
                mock_data = [
                    {"date": "2024-07-01", "IMAGE": 10, "VIDEO": 5, "AUDIO": 2, "Total": 17},
                    {"date": "2024-07-02", "IMAGE": 12, "VIDEO": 6, "AUDIO": 3, "Total": 21},
                    {"date": "2024-07-03", "IMAGE": 8, "VIDEO": 4, "AUDIO": 1, "Total": 13},
                    {"date": "2024-07-04", "IMAGE": 15, "VIDEO": 7, "AUDIO": 4, "Total": 26},
                    {"date": "2024-07-05", "IMAGE": 11, "VIDEO": 5, "AUDIO": 2, "Total": 18},
                ]
                return mock_data
            return list(data_map.values())
        else:
            # TODO: Implement for Org Admin
            raise HTTPException(status_code=501, detail="Org Admin usage over time not yet implemented")

    async def get_admin_organization_budgets(self, current_user: UserModel) -> List[Dict[str, Any]]:
        if current_user.is_super_admin:
            stmt = select(
                Organization.name,
                OrganizationWallet.balance,
                # OrganizationWallet.cumulative_assigned # Assuming this field exists or can be calculated
            ).join(
                OrganizationWallet, Organization.id == OrganizationWallet.organization_id
            ).order_by(Organization.name)
            
            result = await self.db.execute(stmt)
            rows = result.fetchall()
            
            return [
                {
                    "orgName": row.name,
                    "balance": float(row.balance),
                    "budget": 0.0  # Placeholder for budget
                } for row in rows
            ]
        else:
            # TODO: Implement for Org Admin (show only their org)
            raise HTTPException(status_code=501, detail="Org Admin organization budgets not yet implemented")

    async def get_admin_active_roles(self, current_user: UserModel) -> List[Dict[str, Any]]:
        if current_user.is_super_admin:
            # TODO: Replace with actual data from OpenFGA or database
            return [
                {"role": "Super Admin", "count": 2},
                {"role": "Org Admin", "count": 15},
                {"role": "User", "count": 83},
                {"role": "Workspace Admin", "count": 25},
                {"role": "Workspace Member", "count": 60},
            ]
        else:
            raise HTTPException(status_code=501, detail="Org Admin active roles not yet implemented")

    async def get_admin_assigned_over_time(self, current_user: UserModel) -> List[Dict[str, Any]]:
        if not current_user.is_super_admin:
            raise HTTPException(status_code=403, detail="Forbidden")

        stmt = select(
            cast(CreditLog.timestamp, Date).label("date"),
            func.sum(CreditLog.amount).label("total_assigned")
        ).where(
            CreditLog.action == "assign"
        ).group_by(
            cast(CreditLog.timestamp, Date)
        ).order_by(
            cast(CreditLog.timestamp, Date)
        )
        
        result = await self.db.execute(stmt)
        rows = result.fetchall()

        return [
            {"date": row.date.isoformat(), "total_assigned": float(row.total_assigned)}
            for row in rows
        ]
