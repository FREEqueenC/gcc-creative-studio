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

from typing import List, Optional

from fastapi import Depends
from sqlalchemy import select, exists
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.common.base_repository import BaseRepository
from src.database import get_db
from src.workspaces.schema.workspace_model import (
    Workspace,
    WorkspaceMember,
    WorkspaceMemberAssociation,
    WorkspaceModel,
    WorkspaceScopeEnum,
)
from src.workspaces.schema.workspace_model import WorkspaceRoleEnum


class WorkspaceRepository(BaseRepository[Workspace, WorkspaceModel]):
    """
    Repository for all database operations related to the 'workspaces' table.
    """

    def __init__(self, db: AsyncSession = Depends(get_db)):
        """Initializes the repository."""
        super().__init__(model=Workspace, schema=WorkspaceModel, db=db)

    async def get_by_id(self, item_id: int) -> Optional[WorkspaceModel]:
        """Retrieves a single workspace by its ID, ensuring organization is loaded."""
        result = await self.db.execute(
            select(self.model)
            .where(self.model.id == item_id)
            .options(selectinload(self.model.organization))
        )
        workspace = result.scalar_one_or_none()
        if not workspace:
            return None
        return self._map_to_schema(workspace)

    async def get_system_public_workspace(self) -> Optional[WorkspaceModel]:
        """
        Finds the system-wide public workspace (where organization_id is None).
        This is used for storing global templates and system assets.
        """
        result = await self.db.execute(
            select(self.model)
            .where(self.model.scope == WorkspaceScopeEnum.PUBLIC.value)
            .where(self.model.organization_id == None)
            .options(selectinload(self.model.organization))
            .limit(1)
        )
        workspace = result.scalar_one_or_none()
        if not workspace:
            return None
        return self._map_to_schema(workspace)

    async def get_all_workspaces(self) -> List[WorkspaceModel]:
        """Finds all workspaces in the system (for Super Admins)."""
        result = await self.db.execute(
            select(self.model)
            .options(selectinload(self.model.organization))
        )
        workspaces = result.scalars().all()
        return [self._map_to_schema(w) for w in workspaces]

    async def search(
        self, query: str, limit: int = 10, organization_ids: Optional[List[int]] = None
    ) -> List[WorkspaceModel]:
        """
        Searches for workspaces by name (prefix match).
        Optionally filters by organization IDs.
        """
        stmt = select(self.model).where(self.model.name.ilike(f"{query}%"))
        
        if organization_ids:
            stmt = stmt.where(self.model.organization_id.in_(organization_ids))
            
        stmt = stmt.options(selectinload(self.model.organization)).limit(limit)
        
        result = await self.db.execute(stmt)
        workspaces = result.scalars().all()
        return [self._map_to_schema(w) for w in workspaces]

    async def query(self, search_dto: "WorkspaceSearchDto") -> "PaginationResponseDto[WorkspaceModel]":
        """
        Performs a paginated query for workspaces.
        """
        from src.workspaces.dto.workspace_search_dto import WorkspaceSearchDto
        from src.common.dto.pagination_response_dto import PaginationResponseDto
        from sqlalchemy import func

        # 1. Build Query
        query = select(self.model).options(selectinload(self.model.organization))

        if search_dto.name:
            query = query.where(self.model.name.ilike(f"%{search_dto.name}%"))
        
        if search_dto.organization_id:
            query = query.where(self.model.organization_id == search_dto.organization_id)
        elif search_dto.organization_ids:
            query = query.where(self.model.organization_id.in_(search_dto.organization_ids))

        if search_dto.ids:
            query = query.where(self.model.id.in_(search_dto.ids))

        # 2. Count
        count_query = select(func.count()).select_from(query.subquery())
        count_result = await self.db.execute(count_query)
        total_count = count_result.scalar_one()

        # 3. Pagination & Ordering
        query = query.order_by(self.model.name.asc())
        query = query.offset(search_dto.offset).limit(search_dto.limit)

        # 4. Execute
        result = await self.db.execute(query)
        workspaces = result.scalars().all()
        
        data = [self._map_to_schema(w) for w in workspaces]

        # 5. Response
        page = (search_dto.offset // search_dto.limit) + 1
        page_size = search_dto.limit
        total_pages = (total_count + page_size - 1) // page_size

        return PaginationResponseDto[WorkspaceModel](
            count=total_count,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
            data=data,
        )

    async def create(
        self, schema: WorkspaceModel, initial_members: List[WorkspaceMember] = []
    ) -> WorkspaceModel:
        """
        Creates a new workspace and handles the members association manually.
        """
        # Convert Pydantic schema to dict
        data = schema.model_dump(exclude_unset=True)
        
        # Remove id if present and None
        if data.get("id") is None:
            data.pop("id", None)
            
        # Create Workspace instance
        db_item = self.model(**data)
        
        # Handle members manually
        for member in initial_members:
            association = WorkspaceMemberAssociation(
                user_id=member.user_id,
                role=member.role
            )
            db_item.members.append(association)

        self.db.add(db_item)
        await self.db.commit()
        
        # Re-fetch to ensure relationships (organization) are loaded
        return await self.get_by_id(db_item.id) # type: ignore

    async def add_member_to_workspace(
        self, workspace_id: int, member: WorkspaceMember, user_id: int
    ) -> Optional[WorkspaceModel]:
        """
        Atomically adds a new member to a workspace's 'members' list.
        """
        # Fetch the workspace
        result = await self.db.execute(
            select(self.model)
            .where(self.model.id == workspace_id)
            .options(selectinload(self.model.organization))
        )
        workspace = result.scalar_one_or_none()
        if not workspace:
            return None

        # Check if user is already a member
        # We can check the relationship or query the association table directly.
        # Since we have lazy="selectin", workspace.members should be loaded.
        existing_member = next((m for m in workspace.members if m.user_id == user_id), None)
        
        if not existing_member:
            # Create new association
            new_association = WorkspaceMemberAssociation(
                workspace_id=workspace_id,
                user_id=user_id,
                role=member.role
            )
            workspace.members.append(new_association)
            await self.db.commit()
            await self.db.refresh(workspace)
        
        # We need to map the SQLAlchemy models back to the Pydantic model
        return self._map_to_schema(workspace)

    async def update_member_role(self, workspace_id: int, user_id: int, role: WorkspaceRoleEnum) -> Optional[WorkspaceModel]:
        """Updates a user's role in a workspace."""
        from sqlalchemy import update
        
        # Update the role in the association table
        stmt = (
            update(WorkspaceMemberAssociation)
            .where(WorkspaceMemberAssociation.workspace_id == workspace_id)
            .where(WorkspaceMemberAssociation.user_id == user_id)
            .values(role=role.value)
        )
        
        result = await self.db.execute(stmt)
        await self.db.commit()
        
        if result.rowcount == 0:
            return None
            
        # Return the updated workspace
        return await self.get_by_id(workspace_id)

    async def update_owner(self, workspace_id: int, new_owner_id: int) -> Optional[WorkspaceModel]:
        """Updates the owner of a workspace."""
        from sqlalchemy import update
        
        stmt = (
            update(self.model)
            .where(self.model.id == workspace_id)
            .values(owner_id=new_owner_id)
        )
        
        result = await self.db.execute(stmt)
        await self.db.commit()
        
        if result.rowcount == 0:
            return None
            
        return await self.get_by_id(workspace_id)

    async def find_by_member_id(self, user_id: int) -> List[WorkspaceModel]:
        """Finds all workspaces where the user is a member."""
        result = await self.db.execute(
            select(self.model)
            .join(WorkspaceMemberAssociation)
            .where(WorkspaceMemberAssociation.user_id == user_id)
            .options(selectinload(self.model.organization))
        )
        workspaces = result.scalars().all()
        return [self._map_to_schema(w) for w in workspaces]

    async def is_member(self, workspace_id: int, user_id: int) -> bool:
        """Checks if a user is a member of a workspace."""
        result = await self.db.execute(
            select(exists().where(
                WorkspaceMemberAssociation.workspace_id == workspace_id,
                WorkspaceMemberAssociation.user_id == user_id
            ))
        )
        return result.scalar()

    async def get_scope(self, workspace_id: int) -> Optional[str]:
        """Retrieves the scope of a workspace."""
        result = await self.db.execute(
            select(self.model.scope).where(self.model.id == workspace_id)
        )
        return result.scalar_one_or_none()

    async def get_public_workspace_by_org_id(self, org_id: int) -> Optional[WorkspaceModel]:
        """Finds the public workspace for a specific organization."""
        result = await self.db.execute(
            select(self.model)
            .where(self.model.organization_id == org_id)
            .where(self.model.scope == WorkspaceScopeEnum.PUBLIC.value)
            .options(selectinload(self.model.organization))
        )
        workspace = result.scalar_one_or_none()
        if not workspace:
            return None
        return self._map_to_schema(workspace)

    async def find_accessible_by_user_and_orgs(
        self, user_id: int, org_ids: List[int], admin_org_ids: Optional[List[int]] = None
    ) -> List[WorkspaceModel]:
        """
        Finds workspaces that are either:
        1. Explicitly joined by the user (member).
        2. Public workspaces belonging to one of the user's organizations.
        3. Any workspace belonging to an organization where the user is an Admin.
        """
        # Condition 1: User is a member
        member_condition = self.model.members.any(WorkspaceMemberAssociation.user_id == user_id)
        
        conditions = [member_condition]

        # Condition 2: Public and in user's orgs
        if org_ids:
            org_public_condition = (self.model.organization_id.in_(org_ids)) & (self.model.scope == WorkspaceScopeEnum.PUBLIC.value)
            conditions.append(org_public_condition)
            
        # Condition 3: Any workspace in admin orgs
        if admin_org_ids:
            admin_org_condition = self.model.organization_id.in_(admin_org_ids)
            conditions.append(admin_org_condition)

        # Combine with OR
        from sqlalchemy import or_
        combined_condition = or_(*conditions)

        result = await self.db.execute(
            select(self.model)
            .where(combined_condition)
            .options(selectinload(self.model.organization))
        )
        workspaces = result.scalars().all()
        return [self._map_to_schema(w) for w in workspaces]

    def _map_to_schema(self, workspace: Workspace) -> WorkspaceModel:
        """Helper to map SQLAlchemy Workspace to Pydantic WorkspaceModel."""
        # Create the Pydantic model
        workspace_dict = {
            "id": workspace.id,
            "name": workspace.name,
            "owner_id": workspace.owner_id,
            "scope": workspace.scope,
            "organization_id": workspace.organization_id,
            "created_at": workspace.created_at,
            "updated_at": workspace.updated_at
        }
        
        # Map organization name if available
        if workspace.organization:
            workspace_dict["organization_name"] = workspace.organization.name
            
        # Map members
        if workspace.members:
            workspace_dict["members"] = [
                {
                    "user_id": m.user_id,
                    "email": m.email, # Uses the property on Association
                    "role": m.role
                }
                for m in workspace.members
            ]
        
        return self.schema.model_validate(workspace_dict)
        
    async def delete_with_members(self, workspace_id: int) -> bool:
        """Deletes a workspace and all its members."""
        from sqlalchemy import delete
        
        # Delete members first
        await self.db.execute(
            delete(WorkspaceMemberAssociation).where(WorkspaceMemberAssociation.workspace_id == workspace_id)
        )
        
        # Delete workspace
        await self.db.execute(
            delete(self.model).where(self.model.id == workspace_id)
        )
        await self.db.commit()
        return True
