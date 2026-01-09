from fastapi import APIRouter, Request, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from src.auth.auth_service import login_google, auth_callback, get_current_user

router = APIRouter(prefix="/api", tags=["Authentication"])

@router.get("/login/google")
async def login(request: Request):
    return await login_google(request)

@router.get("/auth/callback", name="auth_callback")
async def callback(request: Request):
    user_info = await auth_callback(request)
    # Store user info in session
    # We strip sensitive tokens before storing in session if possible, 
    # but authlib's userinfo is usually safe.
    # We might want to map it to our UserProfile model.
    request.session["user"] = user_info
    
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
async def get_me(user: dict = Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return user
