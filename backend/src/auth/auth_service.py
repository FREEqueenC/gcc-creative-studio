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
# from src.users.google_directory_service import google_directory_service

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

import logging
logger = logging.getLogger(__name__)

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
    
    return user_info

from src.auth.session import get_session_user
from src.core.fga import check_permission, fga_client



async def get_current_user(
    user_data: Optional[Dict[str, Any]] = Depends(get_session_user),
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
    user_model = await user_service.create_user_if_not_exists(
        email=email,
        name=user_data.get("name", ""),
        picture=user_data.get("picture", ""),
    )

    # NOTE: Organization and Workspace initialization is now handled in the auth_callback
    # to prevent race conditions from parallel frontend requests.

    # Check if user is Super Admin (Platform Level)
    # We must use the DB ID because that's what we write to FGA
    # Construct a minimal user dict with the correct ID for the check
    check_user = {"id": str(user_model.id)}
    is_super_admin = await check_permission(check_user, "platform", "creative-studio", "super_admin")
    user_model.is_super_admin = is_super_admin

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


