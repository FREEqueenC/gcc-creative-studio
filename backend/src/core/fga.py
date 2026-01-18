import os
import logging
from typing import List, Optional, Dict, Any, Union
from fastapi import Depends, HTTPException, status
from openfga_sdk import ClientConfiguration, OpenFgaClient
from openfga_sdk.credentials import Credentials

from src.auth.session import get_session_user
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

class FGAClientWrapper:
    def __init__(self):
        self._client = None

    def set_client(self, client: OpenFgaClient):
        self._client = client

    async def check(self, body):
        if not self._client:
             # Fallback or error if not initialized
             # For now, we assume it will be initialized in lifespan
             # But if we really need to, we could try to init here, but that risks the loop issue again if called too early.
             # However, check() is async, so we are in a loop.
             # But we want to avoid implicit init if possible.
             logger.warning("FGA Client not initialized, returning False")
             from openfga_sdk.models.check_response import CheckResponse
             return CheckResponse(allowed=False)
        return await self._client.check(body)

    async def write(self, body):
        if not self._client:
            logger.warning("FGA Client not initialized, skipping write")
            return
        return await self._client.write(body)

    async def list_objects(self, body):
        if not self._client:
            logger.warning("FGA Client not initialized, returning empty list")
            from openfga_sdk.models.list_objects_response import ListObjectsResponse
            return ListObjectsResponse(objects=[])
        return await self._client.list_objects(body)

    async def read(self, body):
        if not self._client:
            logger.warning("FGA Client not initialized, returning empty response")
            from openfga_sdk.models.read_response import ReadResponse
            return ReadResponse(tuples=[])
        return await self._client.read(body)

fga_client = FGAClientWrapper()

class FgaPermissionChecker:
    def __init__(self, object_type: str, relation: str):
        self.object_type = object_type
        self.relation = relation

    async def __call__(
        self, 
        obj_id: str, # We might need to extract this from path params. 
                     # But FastAPI dependencies don't easily get path params unless we use Request.
        request: Any = None, # We can get Request if needed
        user: Optional[Dict[str, Any]] = Depends(get_session_user)
    ):
        # This is a bit tricky as a generic dependency because we need the object ID.
        # Usually we use a closure or a class that takes the ID source.
        # But for now, let's assume we pass the ID manually or use a specific checker per route.
        pass

# Better approach: A dependency that returns a checker function, 
# or a function that takes the object ID and user.

async def check_permission(
    user: Union[Dict[str, Any], UserModel],
    object_type: str,
    object_id: str,
    relation: str,
) -> bool:
    if not user:
        return False

    if isinstance(user, UserModel):
        # BREAK GLASS: Super Admin bypass
        if user.is_super_admin:
            return True
            
        user_id = str(user.id)
        # User requested to skip groups for now when using UserModel
        groups = []
    else:
        user_id = user.get("sub") or user.get("id") # 'sub' is standard OIDC subject
        groups = user.get("groups", [])

    if not user_id:
        return False
        
    # Construct Contextual Tuples from Groups
    # User groups should be in user dict (from session)
    contextual_tuples = []
    
    # For every group, add { user: "user:<id>", relation: "member", object: "group:<group_email>" }
    # Actually, usually contextual tuples are used to assert membership in the group FOR THIS REQUEST.
    # So we say "User X is member of Group Y" contextually.
    
    from openfga_sdk.client.models import ClientCheckRequest, ClientTuple

    for group in groups:
        contextual_tuples.append(ClientTuple(
            user=f"user:{user_id}",
            relation="member",
            object=f"group:{group}",
        ))

    try:
        # Check permission
        request = ClientCheckRequest(
            user=f"user:{user_id}",
            relation=relation,
            object=f"{object_type}:{object_id}",
            contextual_tuples=contextual_tuples if contextual_tuples else None
        )
        
        response = await fga_client.check(request)
        return response.allowed
    except Exception as e:
        logger.error(f"FGA Check failed: {e}")
        return False

# Dependency factory
def require_permission(object_type: str, relation: str, param_name: str = "id"):
    async def dependency(
        request: Any, # FastAPI Request
        user: Optional[Dict[str, Any]] = Depends(get_session_user)
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
