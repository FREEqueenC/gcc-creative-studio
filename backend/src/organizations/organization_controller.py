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

from fastapi import APIRouter, Depends, HTTPException, status

from src.auth.auth_service import get_current_user
from src.users.user_model import UserModel
from src.common.dto.pagination_response_dto import PaginationResponseDto
from src.organizations.dto.organization_search_dto import OrganizationSearchDto
from src.organizations.dto.update_organization_role_dto import UpdateOrganizationRoleDto
from src.organizations.dto.update_organization_dto import UpdateOrganizationDto
from src.organizations.organization_model import OrganizationModel, OrganizationMemberViewModel
from src.organizations.organization_service import OrganizationService

router = APIRouter(
    prefix="/api/organizations",
    tags=["Organizations"],
)

@router.get(
    "",
    response_model=PaginationResponseDto[OrganizationModel],
    summary="List Organizations (Admin Only)",
)
async def list_organizations(
    search_params: OrganizationSearchDto = Depends(),
    organization_service: OrganizationService = Depends(),
    current_user: UserModel = Depends(get_current_user),
):
    """
    Retrieves a paginated list of organizations.
    - Super Admins: Can see all organizations.
    - Org Admins: Can see only organizations they administer.
    """
    return await organization_service.get_organizations_for_admin(current_user, search_params)
    
@router.get(
    "/{org_id}",
    response_model=OrganizationMemberViewModel,
    summary="Get Organization by ID",
)
async def get_organization(
    org_id: int,
    organization_service: OrganizationService = Depends(),
    current_user: UserModel = Depends(get_current_user),
):
    """
    Retrieves a single organization by ID.
    - User must be a member of the organization.
    """
    org = await organization_service.get_organization_by_id(org_id, current_user.id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    return org

@router.put(
    "/{org_id}/users/{user_id}/role",
    response_model=OrganizationModel,
    summary="Update Member Role",
)
async def update_member_role(
    org_id: int,
    user_id: int,
    body: "UpdateOrganizationRoleDto",
    organization_service: OrganizationService = Depends(),
    current_user: UserModel = Depends(get_current_user),
):
    """
    Updates a user's role in an organization (e.g. promote to Admin, demote to Member).
    - Requires Super Admin or Organization Admin permissions.
    """
    return await organization_service.update_member_role(
        org_id, user_id, body.role, current_user
    )

@router.put(
    "/{org_id}",
    response_model=OrganizationModel,
    summary="Update Organization",
)
async def update_organization(
    org_id: int,
    body: UpdateOrganizationDto,
    organization_service: OrganizationService = Depends(),
    current_user: UserModel = Depends(get_current_user),
):
    """
    Updates an organization's details (name, description, logo).
    - Requires 'can_edit_organization' permission (Admin/Owner).
    - Domain cannot be changed.
    """
    return await organization_service.update_organization(
        org_id, body, current_user
    )
