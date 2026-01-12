from fastapi import APIRouter, Request, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from src.auth.auth_service import login_google, auth_callback, get_current_user
from src.users.user_service import UserService
from src.auth.session import get_session_user
from src.auth.dto.permission_check_dto import PermissionCheckDto
from src.core.fga import check_permission

router = APIRouter(prefix="/api", tags=["Authentication"])

@router.get("/login/google")
async def login(request: Request):
    return await login_google(request)

@router.get("/auth/callback", name="auth_callback")
async def callback(
    request: Request,
    user_service: UserService = Depends(),
):
    user_info = await auth_callback(request)
    # Store user info in session
    request.session["user"] = user_info
    
    # Create user immediately to prevent race conditions on frontend load
    email = user_info.get("email")
    name = user_info.get("name", "")
    picture = user_info.get("picture", "")
    
    if email:
        await user_service.create_user_if_not_exists(email, name, picture)
    
    # Redirect to frontend
    # In production, this should be the frontend URL.
    # We default to http://localhost:4200 for local development.
    import os
    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:4200")
    return RedirectResponse(url=frontend_url) 

@router.get("/logout")
async def logout(request: Request):
    request.session.pop("user", None)
    return RedirectResponse(url="/")

@router.get("/me")
async def get_me(user = Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return user

@router.post("/auth/check-permission")
async def check_user_permission(
    check_dto: PermissionCheckDto,
    user: dict = Depends(get_session_user)
):
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    
    allowed = await check_permission(
        user=user,
        object_type=check_dto.object_type,
        object_id=check_dto.object_id,
        relation=check_dto.relation
    )
    return {"allowed": allowed}
