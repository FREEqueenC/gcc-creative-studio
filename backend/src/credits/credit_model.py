# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import datetime
from typing import Optional, List
from sqlalchemy import String, func, DateTime, ForeignKey, Numeric, Integer, Enum as SQLAlchemyEnum, PrimaryKeyConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base
from src.credits.dto.price_catalog_dto import ModelCategoryEnum

class PriceCatalog(Base):
    """
    Catalog of prices for different models/services and categories.
    """
    __tablename__ = "price_catalog"

    model_id: Mapped[str] = mapped_column(String, nullable=False)
    category: Mapped[ModelCategoryEnum] = mapped_column(SQLAlchemyEnum(ModelCategoryEnum), nullable=False, index=True)
    cost: Mapped[float] = mapped_column(Numeric(10, 4), nullable=False)

    __table_args__ = (PrimaryKeyConstraint('model_id', 'category'),)
    
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        insert_default=func.now(),
        server_default=func.now()
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        insert_default=func.now(),
        onupdate=func.now(),
        server_default=func.now()
    )


class UserWallet(Base):
    """
    Wallet for a specific user.
    """
    __tablename__ = "user_wallets"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    balance: Mapped[float] = mapped_column(Numeric(10, 4), default=0.0, nullable=False)
    cumulative_spend: Mapped[float] = mapped_column(Numeric(10, 4), default=0.0, nullable=False)
    expires_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        insert_default=func.now(),
        server_default=func.now()
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        insert_default=func.now(),
        onupdate=func.now(),
        server_default=func.now()
    )

    # Relationships
    user: Mapped["User"] = relationship(back_populates="wallet")


class OrganizationWallet(Base):
    """
    Wallet for a specific organization.
    """
    __tablename__ = "organization_wallets"

    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), primary_key=True)
    balance: Mapped[float] = mapped_column(Numeric(10, 4), default=0.0, nullable=False)
    cumulative_spend: Mapped[float] = mapped_column(Numeric(10, 4), default=0.0, nullable=False)
    expires_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        insert_default=func.now(),
        server_default=func.now()
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        insert_default=func.now(),
        onupdate=func.now(),
        server_default=func.now()
    )

    # Relationships
    organization: Mapped["Organization"] = relationship(back_populates="wallet")


class CreditLog(Base):
    """
    Log of all credit transactions (spend, assign, etc.).
    """
    __tablename__ = "credit_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    action: Mapped[str] = mapped_column(String, nullable=False) # 'spend', 'assign', 'expire'
    amount: Mapped[float] = mapped_column(Numeric(10, 4), nullable=False)
    
    # Who performed the action (optional, e.g. system or admin)
    performed_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    
    # Which wallet was affected (one of these should be set)
    target_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    target_org_id: Mapped[Optional[int]] = mapped_column(ForeignKey("organizations.id"), nullable=True)
    
    # Metadata
    model_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    
    timestamp: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        insert_default=func.now(),
        server_default=func.now(),
        index=True
    )

    # Relationships
    performed_by: Mapped["User"] = relationship(foreign_keys=[performed_by_user_id])
    target_user: Mapped["User"] = relationship(foreign_keys=[target_user_id], back_populates="credit_logs")
    target_org: Mapped["Organization"] = relationship(foreign_keys=[target_org_id])


class BudgetDeposit(Base):
    """
    Record of budget deposits into the system (global budget tracking).
    """
    __tablename__ = "budget_deposits"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    amount_usd: Mapped[float] = mapped_column(Numeric(10, 4), nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    
    timestamp: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        insert_default=func.now(),
        server_default=func.now()
    )
