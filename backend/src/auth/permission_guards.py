"""FastAPI Permission Dependencies.

This module defines reusable FastAPI dependencies (guards) for route protection.
It uses the OpenFGA client to enforce fine-grained access control checks,
such as requiring Super Admin status or specific organization roles.
"""

from fastapi import Depends, HTTPException, status
from src.auth.auth_service import get_current_user
from src.users.user_model import UserModel
from src.core.fga import check_permission

async def require_super_admin(user: UserModel = Depends(get_current_user)) -> bool:
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


async def require_admin_access(user: UserModel = Depends(get_current_user)) -> UserModel:
    """
    Ensures the user has SOME admin privileges (Super Admin OR Org Admin).
    """
    # 1. Check if Super Admin
    if user.is_super_admin:
        return user

    # 2. Check if they manage ANY organization
    if user.can_access_admin_panel:
        return user

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Admin privileges required"
    )
