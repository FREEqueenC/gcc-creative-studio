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
from src.organizations.organization_model import OrganizationModel
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
