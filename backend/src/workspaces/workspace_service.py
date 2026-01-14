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

from fastapi import Depends, HTTPException, status

from src.common.email_service import EmailService
from src.users.repository.user_repository import UserRepository
from src.users.user_model import UserModel
from src.workspaces.dto.create_workspace_dto import CreateWorkspaceDto
from src.workspaces.dto.invite_user_dto import InviteUserDto
from src.workspaces.repository.workspace_repository import WorkspaceRepository
from src.workspaces.schema.workspace_model import (
    WorkspaceMember,
    WorkspaceModel,
    WorkspaceRoleEnum,
    WorkspaceScopeEnum
)


from src.core.fga import fga_client
from openfga_sdk.client.models import ClientWriteRequest, ClientTuple

from src.organizations.organization_service import OrganizationService
from src.organizations.organization_model import OrganizationModel

from src.common.permission_service import PermissionService
from src.workspaces.schema.workspace_model import WorkspacePermissions

class WorkspaceService:
    """
    Handles the business logic for workspace management.
    """

    def __init__(
        self,
        workspace_repo: WorkspaceRepository = Depends(),
        user_repo: UserRepository = Depends(),
        email_service: EmailService = Depends(),
        organization_service: OrganizationService = Depends(),
    ):
        self.workspace_repo = workspace_repo
        self.user_repo = user_repo
        self.email_service = email_service
        self.organization_service = organization_service
        self.permission_service = PermissionService()

    async def create_workspace(
        self, user: UserModel, create_dto: CreateWorkspaceDto
    ) -> WorkspaceModel:
        """Creates a new workspace with the creator as the admin."""
        
        # Determine Organization
        org_id = create_dto.organization_id
        if not org_id:
            # Default to user's primary organization
            user_orgs = await self.organization_service.get_user_organizations(user.id)
            if user_orgs:
                org_id = user_orgs[0].id
            else:
                # User must belong to an organization to create a workspace
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="User does not belong to any organization. Please login again or contact support.",
                )
        
        # Double check: If we still don't have an org_id (should be impossible due to above check), fail.
        if not org_id:
             raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Organization ID is required to create a workspace.",
            )

        # 1. Create the owner as the first member of the workspace
        # We use ADMIN role for the creator in the new model
        owner_as_member = WorkspaceMember(
            user_id=user.id, email=user.email, role=WorkspaceRoleEnum.ADMIN
        )

        # 2. Create the new Workspace model instance
        new_workspace = WorkspaceModel(
            name=create_dto.name,
            owner_id=user.id,
            organization_id=org_id, # Might be None if we didn't resolve it yet
        )
        created_workspace = await self.workspace_repo.create(new_workspace, initial_members=[owner_as_member])

        # 3. Write tuple to OpenFGA
        try:
            writes = [
                ClientTuple(
                    user=f"user:{user.id}",
                    relation="admin",
                    object=f"workspace:{created_workspace.id}",
                )
            ]
            
            if org_id:
                 writes.append(
                    ClientTuple(
                        user=f"organization:{org_id}",
                        relation="parent",
                        object=f"workspace:{created_workspace.id}",
                    )
                 )

            await fga_client.write(
                ClientWriteRequest(writes=writes)
            )
        except Exception as e:
            # Log error but don't fail creation? Or fail?
            # If FGA fails, we might have inconsistency.
            # Ideally we should rollback or retry.
            # For now, we log.
            print(f"Failed to write tuple to OpenFGA: {e}")
        
        # Populate permissions for the new workspace (Admin)
        created_workspace.permissions = WorkspacePermissions(
            can_manage_members=True,
            can_edit=True,
            can_delete=True,
            can_view_workflows=True,
            can_manage_workflows=True,
            can_view_images=True,
            can_generate_images=True,
            can_view_videos=True,
            can_generate_videos=True,
            can_view_audio=True,
            can_generate_audio=True,
            can_view_vto=True,
            can_generate_vto=True
        )

        return created_workspace

    async def invite_user_to_workspace(
        self,
        workspace_id: int,
        invite_dto: InviteUserDto,
        current_user: UserModel,
    ) -> Optional[WorkspaceModel]:
        """
        Invites a user to a workspace by adding them to the members list.
        This action is restricted to the workspace owner or a system admin.
        """
        # 1. Authorization Check: Verify the inviting user has permission.

        workspace = await self.workspace_repo.get_by_id(workspace_id)
        if not workspace:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Workspace not found.",
            )

        is_system_admin = current_user.is_super_admin
        is_workspace_owner = current_user.id == workspace.owner_id

        if not (is_system_admin or is_workspace_owner):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the workspace owner or a system admin can invite users.",
            )

        # 2. Find the user to be invited by their email
        invited_user = await self.user_repo.get_by_email(invite_dto.email)
        if not invited_user:
            return None  # Or raise an exception (e.g., UserNotFound)

        # 3. Add the new member to the workspace document
        new_member = WorkspaceMember(
            user_id=invited_user.id,
            email=invited_user.email,
            role=invite_dto.role,
        )
        updated_workspace = await self.workspace_repo.add_member_to_workspace(
            workspace_id, new_member, invited_user.id
        )

        # 4. Write tuple to OpenFGA
        if updated_workspace:
            fga_relation = "viewer"
            if invite_dto.role == WorkspaceRoleEnum.EDITOR:
                fga_relation = "editor"
            elif invite_dto.role == WorkspaceRoleEnum.OWNER or invite_dto.role == WorkspaceRoleEnum.ADMIN:
                fga_relation = "owner"
            
            try:
                await fga_client.write(
                    ClientWriteRequest(
                        writes=[
                            ClientTuple(
                                user=f"user:{invited_user.id}",
                                relation=fga_relation,
                                object=f"workspace:{workspace_id}",
                            )
                        ]
                    )
                )
            except Exception as e:
                print(f"Failed to write tuple to OpenFGA: {e}")

            # 5. Send an invitation email to the user.
            self.email_service.send_workspace_invitation_email(
                recipient_email=invited_user.email,
                inviter_name=current_user.name,
                workspace_name=updated_workspace.name,
                workspace_id=workspace_id,
            )
        return updated_workspace

    async def list_workspaces_for_user(self, user: UserModel) -> List[WorkspaceModel]:
        """
        Retrieves all workspaces a user has access to. This includes:
        1. Workspaces where the user is explicitly a member.
        2. Public workspaces within the user's organizations.
        """
        # Check if user is Super Admin
        if user.is_super_admin:
            workspaces = await self.workspace_repo.get_all_workspaces()
        else:
            # Get user's organizations
            user_orgs = await self.organization_service.get_user_organizations(user.id)
            org_ids = [org.id for org in user_orgs]
            
            # Identify organizations where user is Admin
            # We use FGA permissions populated in get_user_organizations
            admin_org_ids = [
                org.id for org in user_orgs 
                if org.permissions and org.permissions.is_admin
            ]
            
            # Fetch accessible workspaces
            workspaces = await self.workspace_repo.find_accessible_by_user_and_orgs(
                user.id, org_ids, admin_org_ids
            )
        
        # Populate permissions for each workspace
        for ws in workspaces:
            perms = await self.permission_service.get_permissions_for_workspace(user.id, ws.id)
            ws.permissions = perms
            
        return workspaces

    async def update_member_role(
        self, workspace_id: int, user_id: int, role: WorkspaceRoleEnum, current_user: UserModel
    ) -> WorkspaceModel:
        """
        Updates a user's role in a workspace.
        - Verifies permissions (Workspace Admin or Owner).
        - Updates DB.
        - Updates OpenFGA.
        """
        from fastapi import HTTPException, status
        
        # 1. Verify Permissions
        # Check if user is Workspace Admin or Owner
        is_admin = await self.permission_service.has_permission(
            current_user, "workspace", str(workspace_id), "admin"
        )
        
        if not is_admin:
             raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to update member role."
            )

        # 2. Update DB
        updated_workspace = await self.repo.update_member_role(workspace_id, user_id, role)
        if not updated_workspace:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Workspace or user not found."
            )

        # 3. Update OpenFGA
        # Remove old roles (viewer, editor, admin)
        try:
            await fga_client.write(
                ClientWriteRequest(
                    deletes=[
                        ClientTuple(
                            user=f"user:{user_id}",
                            relation="viewer",
                            object=f"workspace:{workspace_id}",
                        ),
                        ClientTuple(
                            user=f"user:{user_id}",
                            relation="editor",
                            object=f"workspace:{workspace_id}",
                        ),
                        ClientTuple(
                            user=f"user:{user_id}",
                            relation="admin",
                            object=f"workspace:{workspace_id}",
                        )
                    ]
                )
            )
            
            # Add new role
            # Map Enum to FGA relation
            relation = role.value # viewer, editor, admin
            
            await fga_client.write(
                ClientWriteRequest(
                    writes=[
                        ClientTuple(
                            user=f"user:{user_id}",
                            relation=relation,
                            object=f"workspace:{workspace_id}",
                        )
                    ]
                )
            )
        except Exception as e:
            print(f"Failed to update OpenFGA tuples: {e}")
            
        return updated_workspace

    async def search_workspaces(self, user: UserModel, query: str) -> List[WorkspaceModel]:
        """
        Searches for workspaces based on user role.
        - Super Admin: Can search all workspaces.
        - Org Admin: Can search workspaces in their organizations.
        - Others: Cannot search (returns empty list or raises error).
        
        Optimization: Returns empty list if query is less than 3 characters.
        """
        if not query or len(query.strip()) < 3:
            return []

        if user.is_super_admin:
            return await self.workspace_repo.search(query)
        
        # Check if user is an admin of any organization
        # We need to check the roles in user.organizations
        admin_org_ids = [
            org.id for org in user.organizations 
            if org.role == "admin" # Assuming 'admin' is the role string, check OrganizationRoleEnum
        ]
        
        if admin_org_ids:
            return await self.workspace_repo.search(query, organization_ids=admin_org_ids)
            
        # Regular users cannot search for now
        return []

    async def get_workspaces_for_admin(
        self, user: UserModel, search_dto: "WorkspaceSearchDto"
    ) -> "PaginationResponseDto[WorkspaceModel]":
        """
        Retrieves workspaces for admin view.
        - Super Admin: All workspaces.
        - Org Admin: Only workspaces in their organizations.
        """
        from src.common.dto.pagination_response_dto import PaginationResponseDto
        
        if user.is_super_admin:
            # No restriction
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
            
            # If organization_id is passed, ensure it's allowed
            if search_dto.organization_id:
                if search_dto.organization_id not in admin_org_ids:
                     return PaginationResponseDto(
                        count=0, page=1, page_size=search_dto.limit, total_pages=0, data=[]
                    )
            else:
                # If no specific org, we must filter by ALL admin orgs.
                search_dto.organization_ids = admin_org_ids
        
        return await self.workspace_repo.query(search_dto)

    async def ensure_default_workspaces(self, user: UserModel, org: OrganizationModel):
        """
        Ensures the user has the required default workspaces for their organization.
        - Enterprise Org:
            1. Public Workspace (Org-wide, shared)
            2. Personal Workspace (Private, user-specific)
        - Personal Org:
            1. Personal Workspace (Private)
        """
        # 1. Ensure Personal Workspace
        # Check if user already has a private workspace in this org
        user_workspaces = await self.workspace_repo.find_by_member_id(user.id)
        personal_workspace = next(
            (w for w in user_workspaces if w.organization_id == org.id and w.scope == WorkspaceScopeEnum.PRIVATE and w.owner_id == user.id),
            None
        )
        
        if not personal_workspace:
            # Create Personal Workspace
            ws_name = f"{user.name}'s Workspace" if user.name else "My Workspace"
            await self.create_workspace(
                user,
                CreateWorkspaceDto(
                    name=ws_name,
                    organization_id=org.id,
                    scope=WorkspaceScopeEnum.PRIVATE
                )
            )

        # 2. Ensure Public Workspace (Only for Enterprise Orgs)
        if org.domain: # Enterprise Org has a domain
            public_ws = await self.workspace_repo.get_public_workspace_by_org_id(org.id)
            
            if not public_ws:
                # Create Public Workspace for the Org
                ws_name = f"{org.name} Public Workspace"
                created_public_ws = await self.create_workspace(
                    user,
                    CreateWorkspaceDto(
                        name=ws_name,
                        organization_id=org.id,
                        scope=WorkspaceScopeEnum.PUBLIC
                    )
                )
                public_ws = created_public_ws
            
            # Ensure user is a member of this public workspace (so it shows up in their list)
            # Even if it's public, our list_workspaces_for_user logic might rely on membership for now?
            # Actually list_workspaces_for_user fetches ALL public workspaces globally.
            # We should probably refine that to only fetch Global Public + Org Public.
            # But for now, let's just ensure they are a member to be safe and explicit.
            # is_member = await self.workspace_repo.is_member(public_ws.id, user.id)
            # if not is_member:
            #    # Add as viewer
            #    member = WorkspaceMember(user_id=user.id, email=user.email, role=WorkspaceRoleEnum.VIEWER)
            #    await self.workspace_repo.add_member_to_workspace(public_ws.id, member, user.id)
            pass

