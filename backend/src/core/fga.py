import os
import logging
from typing import List, Optional, Dict, Any
from fastapi import Depends, HTTPException, status
from openfga_sdk import ClientConfiguration, OpenFgaClient
from openfga_sdk.credentials import Credentials

from src.auth.auth_service import get_current_user
from src.users.user_model import UserModel

logger = logging.getLogger(__name__)

OPENFGA_API_URL = os.getenv("OPENFGA_API_URL", "http://localhost:8080") # Default or from env
OPENFGA_STORE_ID = os.getenv("OPENFGA_STORE_ID")

if not OPENFGA_STORE_ID:
    logger.warning("OPENFGA_STORE_ID is not set. Authorization checks may fail.")

# Configure FGA Client
config = ClientConfiguration(
    api_url=OPENFGA_API_URL,
    store_id=OPENFGA_STORE_ID,
    # credentials=Credentials(...) # If needed for Auth0 FGA or similar
)

fga_client = OpenFgaClient(config)

class FgaPermissionChecker:
    def __init__(self, object_type: str, relation: str):
        self.object_type = object_type
        self.relation = relation

    async def __call__(
        self, 
        obj_id: str, # We might need to extract this from path params. 
                     # But FastAPI dependencies don't easily get path params unless we use Request.
        request: Any = None, # We can get Request if needed
        user: Optional[Dict[str, Any]] = Depends(get_current_user)
    ):
        # This is a bit tricky as a generic dependency because we need the object ID.
        # Usually we use a closure or a class that takes the ID source.
        # But for now, let's assume we pass the ID manually or use a specific checker per route.
        pass

# Better approach: A dependency that returns a checker function, 
# or a function that takes the object ID and user.

async def check_permission(
    user: Dict[str, Any],
    object_type: str,
    object_id: str,
    relation: str,
) -> bool:
    if not user:
        return False

    user_id = user.get("sub") or user.get("id") # 'sub' is standard OIDC subject
    if not user_id:
        return False
        
    # Construct Contextual Tuples from Groups
    # User groups should be in user dict (from session)
    groups = user.get("groups", [])
    contextual_tuples = []
    
    # For every group, add { user: "user:<id>", relation: "member", object: "group:<group_email>" }
    # Wait, the prompt says:
    # "For every group in the list, add: { user: "user:<id>", relation: "member", object: "group:<group_email>" }"
    # Actually, usually contextual tuples are used to assert membership in the group FOR THIS REQUEST.
    # So we say "User X is member of Group Y" contextually.
    
    for group in groups:
        contextual_tuples.append({
            "user": f"user:{user_id}",
            "relation": "member",
            "object": f"group:{group}",
        })

    try:
        # Check permission
        # user: user:<id>
        # relation: <relation>
        # object: <object_type>:<object_id>
        
        body = {
            "user": f"user:{user_id}",
            "relation": relation,
            "object": f"{object_type}:{object_id}",
            "contextual_tuples": {
                "tuple_keys": contextual_tuples
            }
        }
        
        response = await fga_client.check(body)
        return response.allowed
    except Exception as e:
        logger.error(f"FGA Check failed: {e}")
        return False

# Dependency factory
def require_permission(object_type: str, relation: str, param_name: str = "id"):
    async def dependency(
        request: Any, # FastAPI Request
        user: Optional[Dict[str, Any]] = Depends(get_current_user)
    ):
        if not user:
             raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
        
        # Extract object ID from path parameters
        obj_id = request.path_params.get(param_name)
        if not obj_id:
             # If not in path, maybe query? Or fail.
             # For creation, we might not have ID yet.
             # This dependency is for accessing existing objects.
             raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Missing {param_name}")

        allowed = await check_permission(user, object_type, str(obj_id), relation)
        if not allowed:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
        
        return True
    return dependency
