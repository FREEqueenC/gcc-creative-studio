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
from enum import Enum
from typing import List, Optional, Any

from pydantic import Field, field_validator, BaseModel
from sqlalchemy import String, func, DateTime
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship, Session, with_loader_criteria

from src.common.base_repository import BaseDocument
from src.database import Base
from sqlalchemy import Boolean
from src.credits.credit_model import CreditLog, UserWallet
from src.common.base_dto import BaseDto

class User(Base):
    """
    SQLAlchemy model for the 'users' table.
    """
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    
    # The "Break Glass" flag. It must be kept in sync with OpenFGA's "platform:super_admin" tuple.
    is_super_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    
    # TODO: The roles field is deprecated. Will be removed in future release. Use OpenFGA.
    roles: Mapped[List[str]] = mapped_column(ARRAY(String), default=[])
    name: Mapped[str] = mapped_column(String, default="")
    picture: Mapped[str] = mapped_column(String, default="")
    
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
    deleted_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)

    # Relationships
    organizations: Mapped[List["UserOrganization"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    
    workspaces: Mapped[List["WorkspaceMemberAssociation"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )

    # Credit Economy
    wallet: Mapped["UserWallet"] = relationship(
        "UserWallet",
        back_populates="user",
        cascade="all, delete-orphan",
        uselist=False,
    )
    
    credit_logs: Mapped[List["CreditLog"]] = relationship(
        "CreditLog",
        foreign_keys="CreditLog.target_user_id",
        back_populates="target_user",
        cascade="all, delete-orphan",
    )


class UserOrganizationSummary(BaseModel):
    """
    Summary of an organization a user belongs to, including their role.
    """
    id: int
    name: str
    domain: Optional[str] = None
    role: str


class UserWorkspaceSummary(BaseModel):
    """
    Summary of a workspace a user belongs to, including their role.
    """
    id: int
    name: str
    role: str


class UserWalletDto(BaseDto):
    balance: float
    cumulative_spend: float
    expires_at: Optional[datetime.datetime]


class UserModel(BaseDocument):
    """
    Represents a user document (DTO) for the API.
    """

    # ID is required for Read DTOs
    id: int
    email: str
    # TODO: Deprecated. Will be removed in future release. Use OpenFGA.
    roles: List[str] = Field(default_factory=list, description="Deprecated. Use OpenFGA for authorization.")
    name: str
    picture: str = ""
    is_super_admin: bool = False
    can_access_admin_panel: bool = False
    organizations: List[UserOrganizationSummary] = Field(default_factory=list)
    workspaces: List[UserWorkspaceSummary] = Field(default_factory=list)
    wallet: Optional[UserWalletDto] = None
    deleted_at: Optional[datetime.datetime] = None

    @field_validator('wallet', mode='before')
    @classmethod
    def validate_wallet(cls, v: Any) -> Optional[UserWalletDto]:
        if isinstance(v, UserWallet):
            return UserWalletDto(
                balance=v.balance,
                cumulative_spend=v.cumulative_spend,
                expires_at=v.expires_at,
            )
        if isinstance(v, dict):
            return UserWalletDto(**v)
        if v is None:
            return None
        raise ValueError('Invalid type for wallet')

    @field_validator("roles", mode="after")
    @classmethod
    def default_to_user_role(
        cls, roles: List[str]
    ) -> List[str]:
        """
        Ensures that if the 'roles' list is empty after initialization,
        it defaults to containing the 'user' role.
        """
        if not roles:
            return ["user"]
        return roles

    @field_validator("organizations", mode="before")
    @classmethod
    def map_organizations(cls, v: Any) -> List[UserOrganizationSummary]:
        """
        Maps SQLAlchemy User.organizations (list of UserOrganization) to UserOrganizationSummary list.
        """
        if not v:
            return []
        
        # If it's already a list of dicts or objects (e.g. from Pydantic), return as is
        if isinstance(v, list) and len(v) > 0 and isinstance(v[0], (dict, UserOrganizationSummary)):
            return v

        # Assuming v is a list of UserOrganization SQLAlchemy objects
        summaries = []
        for uo in v:
            # Check if organization is loaded
            if hasattr(uo, "organization") and uo.organization:
                summaries.append(UserOrganizationSummary(
                    id=uo.organization.id,
                    name=uo.organization.name,
                    domain=uo.organization.domain,
                    role=uo.role
                ))
        return summaries

    @field_validator("workspaces", mode="before")
    @classmethod
    def map_workspaces(cls, v: Any) -> List[UserWorkspaceSummary]:
        """
        Maps SQLAlchemy User.workspaces (list of WorkspaceMemberAssociation) to UserWorkspaceSummary list.
        """
        if not v:
            return []
            
        # If it's already a list of dicts or objects, return as is
        if isinstance(v, list) and len(v) > 0 and isinstance(v[0], (dict, UserWorkspaceSummary)):
            return v
            
        # Assuming v is a list of WorkspaceMemberAssociation SQLAlchemy objects
        summaries = []
        for wm in v:
            # Check if workspace is loaded
            if hasattr(wm, "workspace") and wm.workspace:
                summaries.append(UserWorkspaceSummary(
                    id=wm.workspace.id,
                    name=wm.workspace.name,
                    role=wm.role
                ))
        return summaries


# --- Event Listener for Soft Deletes ---
from sqlalchemy import event
import logging

logger = logging.getLogger(__name__)

@event.listens_for(Session, "do_orm_execute")
def _add_user_soft_delete_criteria(execute_state):
    """
    Event listener to automatically filter out soft-deleted Users.
    """
    # Check if we should skip the filter based on execution options
    include_deleted = execute_state.execution_options.get("include_deleted", False)
    
    # Only apply to SELECT statements
    if not execute_state.is_select:
        return

    if include_deleted:
        return

    # Apply the filter using with_loader_criteria, targeting ONLY the User class
    execute_state.statement = execute_state.statement.options(
        with_loader_criteria(
            User,
            lambda cls: cls.deleted_at.is_(None),
            include_aliases=True,
            propagate_to_loaders=True
        )
    )
