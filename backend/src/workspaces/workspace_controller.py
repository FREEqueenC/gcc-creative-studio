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

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status

from src.auth.auth_service import get_current_user
from src.users.user_model import UserModel
from src.common.dto.pagination_response_dto import PaginationResponseDto
from src.workspaces.dto.workspace_search_dto import WorkspaceSearchDto
from src.workspaces.dto.create_workspace_dto import CreateWorkspaceDto
from src.workspaces.dto.invite_user_dto import InviteUserDto
from src.workspaces.dto.update_workspace_role_dto import UpdateWorkspaceRoleDto
from src.workspaces.schema.workspace_model import WorkspaceModel
from src.workspaces.workspace_service import WorkspaceService

router = APIRouter(
    prefix="/api/workspaces",
    tags=["Workspaces"],
    dependencies=[
        Depends(get_current_user)
    ],  # All endpoints require authentication
)


@router.post(
    "",
    response_model=WorkspaceModel,
    status_code=status.HTTP_201_CREATED,
    summary="Create a New Workspace",
)
async def create_workspace(
    create_dto: CreateWorkspaceDto,
    current_user: UserModel = Depends(get_current_user),
    workspace_service: WorkspaceService = Depends(),
):
    """
    Creates a new private workspace for the currently authenticated user.
    The creator is automatically assigned as the 'OWNER'.
    """
    return await workspace_service.create_workspace(current_user, create_dto)


@router.get(
    "",
    response_model=List[WorkspaceModel],
    summary="List Workspaces for Current User",
)
async def list_my_workspaces(
    current_user: UserModel = Depends(get_current_user),
    workspace_service: WorkspaceService = Depends(),
):
    """
    Retrieves a list of all workspaces the currently authenticated user
    is a member of.
    """
    return await workspace_service.list_workspaces_for_user(current_user)


@router.get(
    "/admin",
    response_model=PaginationResponseDto[WorkspaceModel],
    summary="List All Workspaces (Admin Only)",
)
async def list_all_workspaces(
    search_params: WorkspaceSearchDto = Depends(),
    workspace_service: WorkspaceService = Depends(),
    current_user: UserModel = Depends(get_current_user),
):
    """
    Retrieves a paginated list of workspaces for admin view.
    - Super Admins: Can see all workspaces.
    - Org Admins: Can see only workspaces in their organizations.
    """
    return await workspace_service.get_workspaces_for_admin(current_user, search_params)


@router.get(
    "/search",
    response_model=List[WorkspaceModel],
    summary="Search Workspaces",
)
async def search_workspaces(
    q: str,
    current_user: UserModel = Depends(get_current_user),
    workspace_service: WorkspaceService = Depends(),
):
    """
    Searches for workspaces by name (prefix match).
    Restricted to Super Admins and Organization Admins.
    """
    return await workspace_service.search_workspaces(current_user, q)


@router.post(
    "/{workspace_id}/invites",
    response_model=WorkspaceModel,
    summary="Invite a User to a Workspace",
)
async def invite_user(
    workspace_id: int,
    invite_dto: InviteUserDto,
    current_user: UserModel = Depends(get_current_user),
    workspace_service: WorkspaceService = Depends(),
):
    """
    Invites a user (by email) to join a specific workspace with a given role.

    This action is restricted to the workspace's OWNER or a system ADMIN.
    It performs a dual-write, updating both the workspace's member list
    and the invited user's list of workspace memberships.
    """
    updated_workspace = await workspace_service.invite_user_to_workspace(
        workspace_id=workspace_id,
        invite_dto=invite_dto,
        current_user=current_user,
    )
    if not updated_workspace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace or user to invite not found.",
        )
    return updated_workspace

@router.put(
    "/{workspace_id}/users/{user_id}/role",
    response_model=WorkspaceModel,
    summary="Update Member Role",
)
async def update_member_role(
    workspace_id: int,
    user_id: int,
    body: "UpdateWorkspaceRoleDto",
    workspace_service: WorkspaceService = Depends(),
    current_user: UserModel = Depends(get_current_user),
):
    """
    Updates a user's role in a workspace (e.g. promote to Admin, demote to Viewer).
    - Requires Workspace Admin or Owner permissions.
    """
    return await workspace_service.update_member_role(
        workspace_id, user_id, body.role, current_user
    )
