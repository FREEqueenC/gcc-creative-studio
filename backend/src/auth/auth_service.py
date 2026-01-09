import os
from typing import Optional, Dict, Any
from authlib.integrations.starlette_client import OAuth
from fastapi import Request, HTTPException, status, Depends
from starlette.config import Config
from starlette.middleware.sessions import SessionMiddleware
from pydantic import BaseModel

# Import UserService to bridge session to DB user
from src.users.user_service import UserService
from src.users.user_model import UserModel

# We will use environment variables for configuration
GOOGLE_TOKEN_AUDIENCE = os.getenv("GOOGLE_TOKEN_AUDIENCE")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")

if not GOOGLE_TOKEN_AUDIENCE or not GOOGLE_CLIENT_SECRET:
    # This might be acceptable during build/test if not running the app, 
    # but critical for runtime. We'll log a warning or just let it fail later if used.
    pass

config = Config(environ=os.environ)
oauth = OAuth(config)

oauth.register(
    name="google",
    client_id=GOOGLE_TOKEN_AUDIENCE,
    client_secret=GOOGLE_CLIENT_SECRET,
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={
        "scope": "openid email profile",
    },
)

class UserProfile(BaseModel):
    id: str
    email: str
    name: str
    picture: Optional[str] = None
    groups: list[str] = []

async def login_google(request: Request):
    # Use API_EXTERNAL_URL to ensure the redirect URI matches what is registered in Google Cloud Console
    # and is accessible by the browser.
    api_external_url = os.getenv("API_EXTERNAL_URL", "http://localhost:9000")
    redirect_uri = f"{api_external_url}/api/auth/callback"
    return await oauth.google.authorize_redirect(request, redirect_uri)

async def auth_callback(request: Request) -> Dict[str, Any]:
    try:
        token = await oauth.google.authorize_access_token(request)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
        ) from e

    user_info = token.get("userinfo")
    if not user_info:
        # Try to fetch userinfo if not in token (though it should be with openid scope)
        # user_info = await oauth.google.userinfo(token=token)
        # For now assume it's there or we fail
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not get user info",
        )
    
    # TODO: Fetch groups if needed. For now we just return user info.
    # If we need to fetch groups from Directory API, we would do it here using the token.
    # For this refactor, we'll start with basic profile.
    
    return user_info

def get_current_user(request: Request) -> Optional[Dict[str, Any]]:
    user = request.session.get("user")
    if not user:
        return None
    return user

async def get_current_user_model(
    user_data: Optional[Dict[str, Any]] = Depends(get_current_user),
    user_service: UserService = Depends(),
) -> UserModel:
    """
    Dependency that returns the UserModel from the database.
    If the user exists in session but not DB, it creates them.
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
    return await user_service.create_user_if_not_exists(
        email=email,
        name=user_data.get("name", ""),
        picture=user_data.get("picture"),
    )

class RoleChecker:
    def __init__(self, allowed_roles: list[str]):
        self.allowed_roles = allowed_roles

    def __call__(self, user: UserModel = Depends(get_current_user_model)) -> UserModel:
        # Check if user has any of the allowed roles
        # User roles are stored as list of strings or Enums in DB
        # UserModel.roles is likely list[UserRoleEnum] or list[str]
        
        # We assume user.roles is a list of Enums or strings.
        # We convert allowed_roles to strings for comparison if needed, 
        # or rely on Enum comparison if allowed_roles are Enums.
        # user_controller passed UserRoleEnum.ADMIN.
        
        for role in self.allowed_roles:
            if role in user.roles:
                return user
                
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operation not permitted",
        )
