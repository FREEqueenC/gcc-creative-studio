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
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel
from sqlalchemy import String, func, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.common.base_repository import BaseDocument
from src.database import Base
from src.users.user_model import User

class OrganizationRoleEnum(str, Enum):
    """Defines the permissions a user has within an organization."""
    MEMBER = "member"
    ADMIN = "admin"
    OWNER = "owner"

class Organization(Base):
    """
    SQLAlchemy model for the 'organizations' table.
    """
    __tablename__ = "organizations"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    # For "Personal" orgs we just use "gmail.com" etc.
    domain: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    
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
    members: Mapped[List["UserOrganization"]] = relationship(
        back_populates="organization",
        cascade="all, delete-orphan",
    )
    workspaces: Mapped[List["Workspace"]] = relationship(
        back_populates="organization",
        cascade="all, delete-orphan",
    )
    owner: Mapped["User"] = relationship(foreign_keys=[owner_id])

class UserOrganization(Base):
    """
    Association table for the many-to-many relationship between Users and Organizations.
    """
    __tablename__ = "user_organizations"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), primary_key=True)
    role: Mapped[OrganizationRoleEnum] = mapped_column(String, default=OrganizationRoleEnum.MEMBER)

    # Relationships
    user: Mapped["User"] = relationship(back_populates="organizations")
    organization: Mapped["Organization"] = relationship(back_populates="members")

class OrganizationPermissions(BaseModel):
    """
    Computed permissions for the current user on this organization.
    """
    # --- Organization Member Management ---
    can_access_admin_panel: bool = False
    can_assign_org_roles: bool = False
    can_invite_org_members: bool = False
    can_add_org_members: bool = False
    can_remove_org_members: bool = False
    can_view_all_org_workspaces: bool = False
    
    # --- Organization Brand Guidelines Management ---
    can_edit_org_brand_guidelines: bool = False
    can_view_org_brand_guidelines: bool = False
    
    model_config = ConfigDict(
        populate_by_name=True,
        alias_generator=to_camel,
    )


class OrganizationModel(BaseDocument):
    """
    DTO for Organization.
    """
    id: int
    name: str
    owner_id: int
    domain: Optional[str] = None
    role: Optional[OrganizationRoleEnum] = Field(
        default=None, 
        description="The role of the current user in this organization (if applicable)."
    )
    permissions: Optional[OrganizationPermissions] = Field(
        default=None,
        description="Computed permissions for the current user."
    )
