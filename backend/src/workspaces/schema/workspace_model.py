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
from sqlalchemy import String, func, ForeignKey, Integer, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.common.base_repository import BaseDocument
from src.database import Base
from src.users.user_model import User
# Import Organization for type hinting if needed, but string reference is fine for relationship
# from src.organizations.organization_model import Organization

class WorkspaceRoleEnum(str, Enum):
    """Defines the permissions a user has within a single workspace."""

    VIEWER = "viewer"
    EDITOR = "editor"
    ADMIN = "admin"
    OWNER = "owner"


class WorkspaceScopeEnum(str, Enum):
    """Defines the overall visibility of the workspace in the application."""

    PUBLIC = "public"  # Visible to everyone (e.g., the "Default Google Workspace" gallery)
    PRIVATE = "private"  # Visible only to users listed in the 'members' list.


class WorkspaceMember(BaseModel):
    """
    An embedded sub-document defining a user's role within this workspace.
    This complete list is stored on the workspace document.
    """

    user_id: int = Field(description="The User ID of the member.")
    email: str = Field(
        description="The member's email (denormalized for display)."
    )
    role: WorkspaceRoleEnum = Field(default=WorkspaceRoleEnum.VIEWER)

    model_config = ConfigDict(
        populate_by_name=True,
        alias_generator=to_camel,
    )


class Workspace(Base):
    """
    SQLAlchemy model for the 'workspaces' table.
    """
    __tablename__ = "workspaces"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    
    # TODO: Nullable for migration, should be required in a couple of months
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), nullable=True)
    scope: Mapped[str] = mapped_column(String, default=WorkspaceScopeEnum.PRIVATE.value)

    # Relationships
    owner: Mapped["User"] = relationship()
    organization: Mapped["Organization"] = relationship(back_populates="workspaces")
    members: Mapped[List["WorkspaceMemberAssociation"]] = relationship(
        back_populates="workspace",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

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


class WorkspaceMemberAssociation(Base):
    """
    Association table for the many-to-many relationship between Users and Workspaces,
    storing the role of the user in the workspace.
    """
    __tablename__ = "workspace_members"

    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    role: Mapped[WorkspaceRoleEnum] = mapped_column(String, default=WorkspaceRoleEnum.VIEWER)

    # Relationships
    workspace: Mapped["Workspace"] = relationship(back_populates="members")
    user: Mapped["User"] = relationship(back_populates="workspaces", lazy="joined")

    @property
    def email(self) -> str:
        """Returns the user's email for Pydantic compatibility."""
        return self.user.email if self.user else "unknown"


class WorkspacePermissions(BaseModel):
    """
    Computed permissions for the current user on this workspace.
    """
    # --- Workspace Member Management ---
    can_assign_ws_roles: bool = False
    can_invite_ws_members: bool = False
    can_add_ws_members: bool = False
    can_edit_ws_members: bool = False
    can_remove_ws_members: bool = False
    
    # --- Workflows Module (Granular) ---
    can_view_ws_workflows: bool = False
    can_execute_ws_workflows: bool = False
    can_edit_ws_workflows: bool = False
    
    # --- Workspace Brand Guidelines Module (Granular) ---
    can_view_ws_brand_guidelines: bool = False
    can_edit_ws_brand_guidelines: bool = False
    
    # --- GenAI Features (Standard) ---
    can_view_images: bool = False
    can_generate_images: bool = False
    can_view_videos: bool = False
    can_generate_videos: bool = False
    can_view_audio: bool = False
    can_generate_audio: bool = False
    can_view_vto: bool = False
    can_generate_vto: bool = False

    model_config = ConfigDict(
        populate_by_name=True,
        alias_generator=to_camel,
    )


class WorkspaceModel(BaseDocument):
    """
    COLLECTION: workspaces (Root-Level Collection)
    Represents a project, team, or folder. Access is controlled by the 'scope'
    and the 'members' list.
    """

    id: Optional[int] = None

    name: str
    owner_id: int = Field(
        description="The user_id of the person who created this workspace."
    )

    scope: WorkspaceScopeEnum = Field(
        default=WorkspaceScopeEnum.PRIVATE,
        description="Public workspaces are visible to all users. Private ones are visible only to members.",
    )
    organization_id: Optional[int] = None
    organization_name: Optional[str] = None
    
    permissions: Optional[WorkspacePermissions] = Field(
        default=None,
        description="Computed permissions for the current user."
    )
    
    members: List[WorkspaceMember] = Field(
        default=[],
        description="List of members in this workspace."
    )
    
    my_ws_role: Optional[WorkspaceRoleEnum] = Field(
        default=None,
        description="The current user's highest effective role on this workspace."
    )
