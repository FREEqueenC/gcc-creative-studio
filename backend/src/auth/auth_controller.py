from fastapi import APIRouter, Request, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from src.auth.auth_service import login_google, auth_callback, get_current_user

router = APIRouter(prefix="", tags=["Authentication"])

@router.get("/login/google")
async def login(request: Request):
    return await login_google(request)

@router.get("/auth/callback")
async def callback(request: Request):
    user_info = await auth_callback(request)
    # Store user info in session
    # We strip sensitive tokens before storing in session if possible, 
    # but authlib's userinfo is usually safe.
    # We might want to map it to our UserProfile model.
    request.session["user"] = user_info
    
    # Redirect to frontend
    # In production, this should be the frontend URL.
    # For now, we can redirect to root or a specific frontend route.
    # We can get the frontend URL from env or referer.
    frontend_url = request.headers.get("referer") or "/"
    # If referer is the login page, we might want to go to home.
    # A safe default is "/" which might be the backend root or proxied frontend.
    # Better: Redirect to a dedicated "login success" page on frontend or just root.
    return RedirectResponse(url="/") 

@router.get("/logout")
async def logout(request: Request):
    request.session.pop("user", None)
    return RedirectResponse(url="/")

@router.get("/me")
async def get_me(user: dict = Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return user
