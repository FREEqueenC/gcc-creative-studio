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

from src.organizations.organization_model import OrganizationModel, OrganizationRoleEnum
from src.organizations.repository.organization_repository import OrganizationRepository
from src.users.user_model import UserModel

GENERIC_DOMAINS = {
    "gmail.com",
    "hotmail.com",
    "outlook.com",
    "yahoo.com",
    "icloud.com",
    "protonmail.com",
    "aol.com",
    "live.com",
    "msn.com",
}

from src.core.fga import fga_client
from openfga_sdk.client.models import ClientWriteRequest, ClientTuple

class OrganizationService:
    """
    Service for managing organizations and user memberships.
    """

    def __init__(self, repo: OrganizationRepository = Depends()):
        self.repo = repo

    async def get_user_organizations(self, user_id: int) -> List[OrganizationModel]:
        """Finds all organizations a user belongs to."""
        return await self.repo.get_user_organizations(user_id)

    async def create_organization(self, schema: OrganizationModel, user_id: int) -> OrganizationModel:
        """Creates a new organization and writes FGA tuples."""
        created_org = await self.repo.create(schema, user_id)
        
        # Write FGA tuple
        try:
            await fga_client.write(
                ClientWriteRequest(
                    writes=[
                        ClientTuple(
                            user=f"user:{user_id}",
                            relation="admin",
                            object=f"organization:{created_org.id}",
                        )
                    ]
                )
            )
        except Exception as e:
            print(f"Failed to write tuple to OpenFGA: {e}")
            
        return created_org

    async def ensure_user_organization(self, user: UserModel) -> OrganizationModel:
        """
        Ensures the user belongs to an appropriate organization based on their email.
        - Enterprise Domain: Auto-joins or creates the Org for that domain.
        - Generic Domain: Auto-creates a "Personal Org" if not exists.
        """
        email_parts = user.email.split("@")
        if len(email_parts) != 2:
            # Fallback for invalid email, treat as generic/personal
            domain = "unknown"
        else:
            domain = email_parts[1].lower()

        if domain in GENERIC_DOMAINS:
            return await self._ensure_personal_org(user)
        else:
            return await self._ensure_enterprise_org(user, domain)

    async def _ensure_personal_org(self, user: UserModel) -> OrganizationModel:
        """Creates or retrieves a personal organization for the user."""
        user_orgs = await self.get_user_organizations(user.id)
        
        # Check if they have an org that looks like a personal org (no domain or specific name)
        if user_orgs:
            personal_org = next((o for o in user_orgs if o.domain is None), None)
            if personal_org:
                return personal_org
        
        # Create Personal Org
        name = f"{user.name}'s Personal Organization" if user.name else "My Personal Organization"
        new_org = OrganizationModel(
            id=0,
            name=name,
            domain=None # Explicitly None for personal orgs
        )
        return await self.create_organization(new_org, user.id)

    async def _ensure_enterprise_org(self, user: UserModel, domain: str) -> OrganizationModel:
        """Joins or creates an organization for the enterprise domain."""
        org = await self.repo.get_by_domain(domain)
        
        if org:
            # Join as MEMBER if not already
            # We need to check if they are already a member to avoid DB constraints or unnecessary writes
            # The repo.add_member handles check? 
            # Repo implementation: "Check if already member... if not existing: append"
            # So it's safe to call.
            await self.repo.add_member(org.id, user.id, OrganizationRoleEnum.MEMBER)
            
            # Write FGA tuple for member
            try:
                await fga_client.write(
                    ClientWriteRequest(
                        writes=[
                            ClientTuple(
                                user=f"user:{user.id}",
                                relation="member",
                                object=f"organization:{org.id}",
                            )
                        ]
                    )
                )
            except Exception as e:
                print(f"Failed to write tuple to OpenFGA: {e}")

            return org
        else:
            # Create new Org as ADMIN
            name = domain.split(".")[0].capitalize()
            new_org = OrganizationModel(
                id=0, # ignored
                name=name,
                domain=domain
            )
            return await self.create_organization(new_org, user.id)
