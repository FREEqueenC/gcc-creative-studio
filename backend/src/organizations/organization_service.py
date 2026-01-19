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
from src.common.consistency_service import ConsistencyService

class OrganizationService:
    """
    Service for managing organizations and user memberships.
    """

    def __init__(
        self, 
        repo: OrganizationRepository = Depends(), 
        db: AsyncSession = Depends(get_db),
        consistency_service: ConsistencyService = Depends()
    ):
        self.repo = repo
        self.db = db
        self.seeder = OrganizationSeeder(db)
        self.user_repo = UserRepository(db)
        self.permission_service = PermissionService()
        self.consistency_service = consistency_service

    async def get_user_organizations(self, user_id: int) -> List[OrganizationModel]:
        """Finds all organizations a user belongs to."""
        orgs = await self.repo.get_user_organizations(user_id)
        
        # Populate permissions for each org
        # TODO: Optimize with a batch call if possible, but for now loop is fine (usually few orgs per user)
        for org in orgs:
            perms = await self.permission_service.get_permissions_for_organization(user_id, org.id)
            org.permissions = perms
            
        return orgs

    async def create_organization(self, schema: OrganizationModel, user_id: int) -> OrganizationModel:
        """Creates a new organization, writes FGA tuples, and seeds default data."""
        
        # 1. Set Owner ID
        schema.owner_id = user_id
        
        # 2. Define DB Operation
        async def db_op() -> OrganizationModel:
            return await self.repo.create(schema, user_id)

        # 3. Define FGA Operation
        async def fga_op(created_org: OrganizationModel):
            await fga_client.write(
                ClientWriteRequest(
                    writes=[
                        ClientTuple(
                            user=f"user:{user_id}",
                            relation="owner",
                            object=f"organization:{created_org.id}",
                        ),
                        # We also add them as admin explicitly, though owner implies admin, 
                        # it's good to be explicit or just rely on owner.
                        # The user asked for owner role. Owner implies Admin in our model.
                        # Let's just write owner.
                    ]
                )
            )

        # 4. Define Rollback Operation
        async def rollback_op(created_org: OrganizationModel):
            if created_org and created_org.id:
                await self.repo.delete(created_org.id)

        # 5. Execute via ConsistencyService
        created_org = await self.consistency_service.perform_dual_write(
            db_op=db_op,
            fga_op=fga_op,
            rollback_op=rollback_op,
            error_message="Failed to create organization."
        )
            
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

        # Populate permissions for the new org (Owner/Admin)
        created_org.permissions = OrganizationPermissions(
            can_assign_org_roles=True,
            can_edit_org_brand_guidelines=True,
            can_view_org_brand_guidelines=True,
            can_view_all_org_workspaces=True,
            can_assign_ws_roles=True,
            can_edit_ws_brand_guidelines=True,
            can_view_ws_brand_guidelines=True,
            can_view_images=True,
            can_generate_images=True,
            can_view_videos=True,
            can_generate_videos=True,
            can_view_audio=True,
            can_generate_audio=True,
            can_view_vto=True,
            can_generate_vto=True,
        )

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
        
        # Check if we are transferring ownership
        is_transferring_ownership = role == OrganizationRoleEnum.OWNER
        previous_owner_id = None
        
        if is_transferring_ownership:
            # We need to find the current owner
            org = await self.repo.get_by_id(org_id)
            if not org:
                 raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found.")
            previous_owner_id = org.owner_id

        # 3. Define DB Operation
        async def db_op() -> OrganizationModel:
            if is_transferring_ownership and previous_owner_id and previous_owner_id != user_id:
                # Demote previous owner to ADMIN
                await self.repo.update_member_role(org_id, previous_owner_id, OrganizationRoleEnum.ADMIN)
                # Update Organization owner_id
                await self.repo.update_owner(org_id, user_id)
            
            updated_org = await self.repo.update_member_role(org_id, user_id, role)
            if not updated_org:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Organization or user not found."
                )
            return updated_org

        # 4. Define FGA Operation
        async def fga_op():
            # If transferring ownership, we need to update the previous owner's FGA tuple too
            if is_transferring_ownership and previous_owner_id and previous_owner_id != user_id:
                # Demote previous owner to ADMIN in FGA
                # We use the same read-delete-write pattern to avoid "tuple already exists" or "tuple not found" errors
                prev_owner_tuples_to_delete = []
                try:
                    response = await fga_client.read(
                        ReadRequestTupleKey(
                            user=f"user:{previous_owner_id}",
                            object=f"organization:{org_id}",
                        )
                    )
                    if response.tuples:
                        for t in response.tuples:
                            prev_owner_tuples_to_delete.append(
                                ClientTuple(
                                    user=t.key.user,
                                    relation=t.key.relation,
                                    object=t.key.object,
                                )
                            )
                except Exception as e:
                    print(f"Failed to read FGA tuples for previous owner: {e}")
                
                if prev_owner_tuples_to_delete:
                    await fga_client.write(
                        ClientWriteRequest(
                            deletes=prev_owner_tuples_to_delete
                        )
                    )

                await fga_client.write(
                    ClientWriteRequest(
                        writes=[
                            ClientTuple(
                                user=f"user:{previous_owner_id}",
                                relation="admin",
                                object=f"organization:{org_id}",
                            )
                        ]
                    )
                )

            # Update target user's FGA tuple
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
                # If we can't read FGA, we shouldn't proceed with write as we might leave garbage
                raise e

            # Delete ALL existing tuples for this user/org
            if tuples_to_delete:
                await fga_client.write(
                    ClientWriteRequest(
                        deletes=tuples_to_delete
                    )
                )
            
            # Write NEW tuple
            relation = "admin" if role == OrganizationRoleEnum.ADMIN else "member"
            if role == OrganizationRoleEnum.OWNER:
                relation = "owner"
                
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

        # 5. Define Rollback Operation
        async def rollback_op():
            print(f"Reverting DB role change for user {user_id} in org {org_id} to {old_role_enum}")
            await self.repo.update_member_role(org_id, user_id, old_role_enum)
            
            if is_transferring_ownership and previous_owner_id:
                # Revert previous owner to OWNER
                await self.repo.update_member_role(org_id, previous_owner_id, OrganizationRoleEnum.OWNER)
                # Revert Org owner_id
                await self.repo.update_owner(org_id, previous_owner_id)

        # 6. Execute via ConsistencyService
        return await self.consistency_service.perform_dual_write(
            db_op=db_op,
            fga_op=fga_op,
            rollback_op=rollback_op,
            error_message="Failed to update permissions."
        )
