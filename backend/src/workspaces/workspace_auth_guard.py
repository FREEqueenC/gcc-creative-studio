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

from typing import Annotated

from fastapi import Depends, HTTPException, status

from src.auth.auth_service import get_current_user
from src.users.user_model import UserModel
from src.workspaces.repository.workspace_repository import WorkspaceRepository
from src.workspaces.schema.workspace_model import (
    WorkspaceModel,
    WorkspaceScopeEnum,
)


class WorkspaceAuth:
    """
    A dependency class that centralizes workspace authorization logic.
    """


    async def authorize(
        self,
        workspace_id: int,
        user: UserModel = Depends(get_current_user),
        workspace_repo: WorkspaceRepository = Depends(),
        permission: str = "viewer",
    ) -> WorkspaceModel | None:
        """
        The core authorization logic. Checks if a user has rights to a workspace.

        Raises HTTPException if unauthorized.
        Returns the WorkspaceModel if authorized.
        """
        # Check scope first (efficient query)
        scope = await workspace_repo.get_scope(workspace_id)

        if scope is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Workspace with ID '{workspace_id}' not found.",
            )

        # Authorization checks using OpenFGA
        # We check if the user has the requested permission (default 'viewer') on the workspace.
        # 'viewer' includes 'editor' and 'admin' via FGA hierarchy.
        
        from src.core.fga import check_permission
        
        is_public = scope == WorkspaceScopeEnum.PUBLIC
        
        # Public workspaces are viewable by everyone, but might require higher permissions for other actions.
        # If permission is 'viewer' and workspace is public, we skip FGA check.
        # If permission is 'admin' or 'editor', we MUST check FGA even if public (usually).
        # Assuming 'public' only implies 'viewer' access.
        
        if not (is_public and permission == "viewer"):
            # Check FGA permission
            # We check the requested relation on 'workspace' object
            has_permission = await check_permission(user, "workspace", str(workspace_id), permission)
            
            if not has_permission:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"You do not have '{permission}' permission on this workspace.",
                )
            
            if not has_permission:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You do not have permission to access this workspace.",
                )

        # If authorized, return the full workspace object
        return await workspace_repo.get_by_id(workspace_id)


# Create a single instance to be used as a dependency
workspace_auth_service = WorkspaceAuth()

# Create an annotated dependency for cleaner use in endpoint signatures
AuthorizedWorkspace = Annotated[
    WorkspaceModel, Depends(workspace_auth_service.authorize)
]
