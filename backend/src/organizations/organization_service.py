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
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.organizations.organization_model import OrganizationModel, OrganizationRoleEnum, OrganizationPermissions
from src.organizations.repository.organization_repository import OrganizationRepository
from src.organizations.organization_seeder import OrganizationSeeder
from src.users.user_model import UserModel
from src.users.repository.user_repository import UserRepository

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

from src.common.permission_service import PermissionService

class OrganizationService:
    """
    Service for managing organizations and user memberships.
    """

    def __init__(self, repo: OrganizationRepository = Depends(), db: AsyncSession = Depends(get_db)):
        self.repo = repo
        self.db = db
        self.seeder = OrganizationSeeder(db)
        self.user_repo = UserRepository(db)
        self.permission_service = PermissionService()

    async def get_user_organizations(self, user_id: int) -> List[OrganizationModel]:
        """Finds all organizations a user belongs to."""
        orgs = await self.repo.get_user_organizations(user_id)
        
        # Populate permissions for each org
        # TODO: Optimize with a batch call if possible, but for now loop is fine (usually few orgs per user)
        for org in orgs:
            perms = await self.permission_service.get_permissions_for_organization(user_id, org.id)
            org.permissions = OrganizationPermissions(**perms)
            
        return orgs

    async def create_organization(self, schema: OrganizationModel, user_id: int) -> OrganizationModel:
        """Creates a new organization, writes FGA tuples, and seeds default data."""
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
            
        # Seed Organization Data (Workspaces, Assets)
        try:
            # We need the full user model for seeding (to set owner)
            user = await self.user_repo.get(user_id)
            if user:
                await self.seeder.seed_organization(created_org.id, user)
            else:
                print(f"User {user_id} not found, skipping seeding for org {created_org.id}")
        except Exception as e:
             print(f"Failed to seed organization {created_org.id}: {e}")

        # Populate permissions for the new org (Admin)
        # TODO: This should be done by FGA, we should use OrganizationPermissions to have it typed safely
        created_org.permissions = {
            "can_assign_org_roles": True,
            "can_edit": True,
            "can_delete": True,
            "can_view_all_org_workspaces": True
        }

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
        # We check user.organizations first (from UserModel)
        if user.organizations:
            personal_org_summary = next((o for o in user.organizations if o.domain is None), None)
            if personal_org_summary:
                # We need to return OrganizationModel, but we only have Summary.
                # We should fetch the full org to be safe and consistent with return type.
                return await self.repo.get_by_id(personal_org_summary.id)

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
            # OPTIMIZATION: Check if user is already a member using the loaded user object
            # This avoids an unnecessary DB call and reduces race condition window
            is_member = any(o.id == org.id for o in user.organizations)
            
            if not is_member:
                # Join as MEMBER if not already
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

            # Populate permissions
            # Since we just added them as member, we can guess, but better to fetch
            perms = await self.permission_service.get_permissions_for_organization(user.id, org.id)
            org.permissions = perms
            
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

            return await self.create_organization(new_org, user.id)

    async def get_organizations_for_admin(
        self, user: UserModel, search_dto: "OrganizationSearchDto"
    ) -> "PaginationResponseDto[OrganizationModel]":
        """
        Retrieves organizations for admin view.
        - Super Admin: All organizations.
        - Org Admin: Only organizations they administer.
        """
        from src.common.dto.pagination_response_dto import PaginationResponseDto
        
        if user.is_super_admin:
            # No restriction on IDs unless passed in search_dto
            pass
        else:
            # Restrict to Org Admin's organizations
            admin_org_ids = [
                org.id for org in user.organizations 
                if org.role == "admin" # Check OrganizationRoleEnum.ADMIN
            ]
            
            if not admin_org_ids:
                 return PaginationResponseDto(
                    count=0, page=1, page_size=search_dto.limit, total_pages=0, data=[]
                )
            
            # If ids were already passed, intersect them? Or override?
            # Usually we override or intersect. Let's intersect to be safe.
            if search_dto.ids:
                search_dto.ids = list(set(search_dto.ids) & set(admin_org_ids))
                if not search_dto.ids:
                     return PaginationResponseDto(
                        count=0, page=1, page_size=search_dto.limit, total_pages=0, data=[]
                    )
            else:
                search_dto.ids = admin_org_ids

        return await self.repo.query(search_dto)

    async def update_member_role(
        self, org_id: int, user_id: int, role: OrganizationRoleEnum, current_user: UserModel
    ) -> OrganizationModel:
        """
        Updates a user's role in an organization.
        - Verifies permissions (Super Admin or Org Admin).
        - Updates DB.
        - Updates OpenFGA.
        """
        from fastapi import HTTPException, status
        from openfga_sdk.client.models import ClientWriteRequest, ClientTuple
        from openfga_sdk.models import ReadRequestTupleKey
        
        # 1. Verify Permissions
        if current_user.id == user_id:
             raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You cannot change your own role."
            )

        if not current_user.is_super_admin:
            # Check if Org Admin
            is_org_admin = await self.permission_service.has_permission(
                current_user, "organization", str(org_id), "admin"
            )
            if not is_org_admin:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Insufficient permissions to update member role."
                )

        # 2. Get Current State (for potential revert and FGA cleanup)
        # Fetch current DB role
        user_orgs = await self.repo.get_user_organizations(user_id)
        current_org_membership = next((o for o in user_orgs if o.id == org_id), None)
        
        if not current_org_membership:
             raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User is not a member of this organization."
            )
        
        old_role_str = current_org_membership.role
        old_role_enum = OrganizationRoleEnum(old_role_str)

        # Fetch current FGA relations to avoid "tuple does not exist" error
        tuples_to_delete = []
        try:
            # Read all tuples for this user and object
            response = await fga_client.read(
                ReadRequestTupleKey(
                    user=f"user:{user_id}",
                    object=f"organization:{org_id}",
                )
            )
            if response.tuples:
                for t in response.tuples:
                    tuples_to_delete.append(
                        ClientTuple(
                            user=t.key.user,
                            relation=t.key.relation,
                            object=t.key.object,
                        )
                    )
        except Exception as e:
            print(f"Failed to read FGA tuples: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to synchronize with authorization system."
            )

        # 3. Update DB
        updated_org = await self.repo.update_member_role(org_id, user_id, role)
        if not updated_org:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Organization or user not found."
            )

        # 4. Update OpenFGA
        try:
            # Delete ALL existing tuples for this user/org
            if tuples_to_delete:
                await fga_client.write(
                    ClientWriteRequest(
                        deletes=tuples_to_delete
                    )
                )
            
            # Write NEW tuple
            relation = "admin" if role == OrganizationRoleEnum.ADMIN else "member"
            await fga_client.write(
                ClientWriteRequest(
                    writes=[
                        ClientTuple(
                            user=f"user:{user_id}",
                            relation=relation,
                            object=f"organization:{org_id}",
                        )
                    ]
                )
            )
        except Exception as e:
            print(f"Failed to update OpenFGA tuples: {e}")
            
            # COMPENSATING TRANSACTION: Revert DB
            print(f"Reverting DB role change for user {user_id} in org {org_id} to {old_role_enum}")
            await self.repo.update_member_role(org_id, user_id, old_role_enum)
            
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update permissions. Changes reverted."
            )
            
        return updated_org
