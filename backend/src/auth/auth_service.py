import os
from typing import Optional, Dict, Any
from fastapi import Request, HTTPException, status, Depends
from pydantic import BaseModel

# Import UserService to bridge session to DB user
from src.users.user_service import UserService
from src.users.user_model import UserModel
from src.organizations.organization_service import OrganizationService
from src.workspaces.workspace_service import WorkspaceService

import logging
logger = logging.getLogger(__name__)

from src.auth.session import get_session_user
from src.core.fga import check_permission, fga_client

async def get_current_user(
    user_data: Optional[Dict[str, Any]] = Depends(get_session_user),
    user_service: UserService = Depends(),
    organization_service: OrganizationService = Depends(),
    workspace_service: WorkspaceService = Depends(),
) -> UserModel:
    """
    Dependency that returns the UserModel from the database.
    If the user exists in session (token claims) but not DB, it creates them.
    If no session, raises 401.
    """
    if not user_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    
    email = user_data.get("email")
    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User email not found in session",
        )

    # Ensure user exists in DB
    # We map 'picture' from Google to 'picture' in DB
    # We map 'name' from Google to 'name' in DB
    user_model = await user_service.create_user_if_not_exists(
        email=email,
        name=user_data.get("name", ""),
        picture=user_data.get("picture", ""),
    )

    # Ensure user belongs to an organization (Personal or Enterprise)
    org = await organization_service.ensure_user_organization(user_model)
    
    # Ensure default workspaces exist (Personal + Public for Enterprise)
    await workspace_service.ensure_default_workspaces(user_model, org)

    # TODO: Fetch groups from Google Directory API in the future
    # We do this here to store them in the session for Contextual Tuples
    # email = user_info.get("email")
    # if email:
    #     try:
    #         groups = google_directory_service.get_user_groups(email)
    #         user_info["groups"] = groups
    #     except Exception as e:
    #         # Log error but don't fail login
    #         # logger.error(f"Failed to fetch groups for {email}: {e}")
    #         user_info["groups"] = []

    # Check if user is Super Admin (Platform Level)
    # We must use the DB ID because that's what we write to FGA
    # Construct a minimal user dict with the correct ID for the check
    check_user = {"id": str(user_model.id)}
    is_super_admin = await check_permission(check_user, "platform", "creative-studio", "super_admin")
    user_model.is_super_admin = is_super_admin or user_model.is_super_admin

    # TODO: No need to force this as is calculated by openfga
    # Check if user can access admin panel
    # Logic: Super Admin OR Admin of ANY Organization
    if is_super_admin:
        user_model.can_access_admin_panel = True
    else:
        # Query FGA for all organizations where user is 'admin'
        from openfga_sdk.client.models import ClientListObjectsRequest
        
        try:
            # We list objects of type 'organization' where user has relation 'can_access_admin_panel'
            req = ClientListObjectsRequest(
                user=f"user:{user_model.id}",
                relation="can_access_admin_panel",
                type="organization"
            )
            resp = await fga_client.list_objects(req)
            # If the list is not empty, they are an admin of at least one org
            user_model.can_access_admin_panel = len(resp.objects) > 0
        except Exception as e:
            # If FGA fails, default to False for safety
            logger.error(f"ERROR: Failed to check admin panel access via FGA: {e}")
            import traceback
            traceback.print_exc()
            user_model.can_access_admin_panel = False

    return user_model
