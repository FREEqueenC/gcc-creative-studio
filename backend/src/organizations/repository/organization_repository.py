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
from src.organizations.organization_model import (
    Organization,
    OrganizationModel,
    UserOrganization,
    OrganizationRoleEnum,
)

class OrganizationRepository(BaseRepository[Organization, OrganizationModel]):
    """
    Repository for all database operations related to the 'organizations' table.
    """

    def __init__(self, db: AsyncSession = Depends(get_db)):
        """Initializes the repository."""
        super().__init__(model=Organization, schema=OrganizationModel, db=db)

    async def get_by_domain(self, domain: str) -> Optional[OrganizationModel]:
        """Finds an organization by its domain."""
        result = await self.db.execute(
            select(self.model).where(self.model.domain == domain)
        )
        org = result.scalar_one_or_none()
        if not org:
            return None
        return self._map_to_schema(org)

    async def create(self, schema: OrganizationModel, user_id: int) -> OrganizationModel:
        """
        Creates a new organization and makes the creating user an ADMIN.
        """
        data = schema.model_dump(exclude_unset=True)
        if data.get("id") is None:
            data.pop("id", None)
            
        db_item = self.model(**data)
        
        # Add creator as ADMIN
        association = UserOrganization(
            user_id=user_id,
            role=OrganizationRoleEnum.ADMIN
        )
        db_item.members.append(association)

        self.db.add(db_item)
        await self.db.commit()
        await self.db.refresh(db_item)
        
        return self._map_to_schema(db_item)

    async def add_member(self, org_id: int, user_id: int, role: OrganizationRoleEnum = OrganizationRoleEnum.MEMBER) -> Optional[OrganizationModel]:
        """Adds a user to an organization."""
        result = await self.db.execute(
            select(self.model)
            .where(self.model.id == org_id)
            .options(selectinload(self.model.members))
        )
        org = result.scalar_one_or_none()
        if not org:
            return None

        # Check if already member
        existing = next((m for m in org.members if m.user_id == user_id), None)
        if not existing:
            association = UserOrganization(
                organization_id=org_id,
                user_id=user_id,
                role=role
            )
            org.members.append(association)
            await self.db.commit()
            await self.db.refresh(org)
            
        return self._map_to_schema(org)

    async def get_user_organizations(self, user_id: int) -> List[OrganizationModel]:
        """Finds all organizations a user belongs to."""
        result = await self.db.execute(
            select(self.model)
            .join(UserOrganization)
            .where(UserOrganization.user_id == user_id)
        )
        orgs = result.scalars().all()
        return [self._map_to_schema(o) for o in orgs]

    def _map_to_schema(self, org: Organization) -> OrganizationModel:
        """Helper to map SQLAlchemy Organization to Pydantic OrganizationModel."""
        org_dict = {
            "id": org.id,
            "name": org.name,
            "domain": org.domain,
        }
        return self.schema.model_validate(org_dict)
