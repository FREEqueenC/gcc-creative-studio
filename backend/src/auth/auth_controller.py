from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import RedirectResponse
from src.auth.auth_service import get_current_user
from src.users.user_service import UserService
from src.organizations.organization_service import OrganizationService
from src.workspaces.workspace_service import WorkspaceService
from src.auth.session import get_session_user
from src.core.fga import check_permission

router = APIRouter()

@router.get("/api/me")
async def get_me(user = Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return user

@router.get("/api/auth/check-permission")
async def check_permission_route(
    object_type: str,
    object_id: str,
    relation: str,
    user = Depends(get_current_user) # Use get_current_user to get the full user model with ID
):
    """
    Checks if the current user has permission on an object.
    """
    allowed = await check_permission(user, object_type, object_id, relation)
    return {"allowed": allowed}
