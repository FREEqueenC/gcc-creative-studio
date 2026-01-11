from fastapi import Depends, HTTPException, status
from src.auth.auth_service import get_current_user_model
from src.users.user_model import UserModel
from src.core.fga import check_permission

async def require_super_admin(user: UserModel = Depends(get_current_user_model)) -> bool:
    """
    Dependency to ensure the current user is a Platform Super Admin.
    Uses the DB ID to check against OpenFGA.
    """
    # We construct a minimal dict with the ID because check_permission expects a dict with "id" or "sub"
    # and we want to ensure it uses the DB ID.
    check_user = {"id": str(user.id)}
    
    allowed = await check_permission(check_user, "platform", "creative-studio", "super_admin")
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Requires Platform Super Admin privileges"
        )
    return True
