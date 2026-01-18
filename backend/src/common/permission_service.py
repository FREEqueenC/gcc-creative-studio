import asyncio
from typing import List, Dict, Any, Type, TypeVar
from openfga_sdk import OpenFgaClient
from openfga_sdk.client.models import ClientCheckRequest
from src.core.fga import fga_client
from typing import Union

import logging
logger = logging.getLogger(__name__)

T = TypeVar("T")

class PermissionService:
    """
    Service to efficiently calculate permissions for resources using OpenFGA.
    Updates:
    - Aligned with Authorization Model (Add-On Gates).
    - Granular permissions (View vs Edit vs Execute).
    """

    def __init__(self, client: OpenFgaClient = None):
        self.client = client or fga_client

    async def get_permissions_for_workspace(self, user_id: int, workspace_id: int) -> Dict[str, bool]:
        """
        Calculates all relevant UI permissions for a single workspace.
        This dictates which buttons/tabs are shown to the user.
        """
        checks = {            
            # --- Workspace Member Management ---
            "can_invite_ws_members": "can_invite_ws_members",
            "can_add_ws_members": "can_add_ws_members",
            "can_remove_ws_members": "can_remove_ws_members",
            "can_assign_ws_roles": "can_assign_ws_roles",
            
            # --- Workflows Module (Granular) ---
            "can_view_ws_workflows": "can_view_ws_workflows",       # Tab visibility
            "can_execute_ws_workflows": "can_execute_ws_workflows", # Run button
            "can_edit_ws_workflows": "can_edit_ws_workflows",       # Builder access

            # --- Brand Guidelines Module (Granular) ---
            "can_view_ws_brand_guidelines": "can_view_ws_brand_guidelines", # View/Download
            "can_edit_ws_brand_guidelines": "can_edit_ws_brand_guidelines", # Upload/Delete
            
            # --- GenAI Features (Standard) ---
            "can_view_images": "can_view_images",
            "can_generate_images": "can_generate_images",
            "can_view_videos": "can_view_videos",
            "can_generate_videos": "can_generate_videos",
            "can_view_audio": "can_view_audio",
            "can_generate_audio": "can_generate_audio",
            "can_view_vto": "can_view_vto",
            "can_generate_vto": "can_generate_vto",
        }
        
        results = await self._batch_check(user_id, "workspace", str(workspace_id), checks)
        return results

    async def get_permissions_for_organization(self, user_id: int, org_id: int) -> Dict[str, bool]:
        """
        Calculates permissions for a single organization.
        """
        checks = {
            # --- Org Management ---
            "can_add_org_members": "admin",
            "can_remove_org_members": "admin",
            "can_assign_org_roles": "admin",
            "can_access_admin_panel": "can_access_admin_panel",
            "can_view_all_org_workspaces": "can_view_all_org_workspaces",

            # --- Org Assets (Granular) ---
            "can_view_org_brand_guidelines": "can_view_org_brand_guidelines",
            "can_edit_org_brand_guidelines": "can_edit_org_brand_guidelines",
        }
        
        results = await self._batch_check(user_id, "organization", str(org_id), checks)
        return results

    async def _batch_check(self, user_id: int, object_type: str, object_id: str, checks: Dict[str, str]) -> Dict[str, bool]:
        """
        Performs parallel FGA checks efficiently.
        
        Args:
            checks: Dict mapping 'ui_permission_name' -> 'fga_relation_name'
        """
        user = f"user:{user_id}"
        obj = f"{object_type}:{object_id}"
        
        # Create coroutines for all checks
        tasks = []
        keys = []
        
        # We assume the client is already configured (ensure asyncio client usage in startup)
        for perm_name, relation in checks.items():
            keys.append(perm_name)
            tasks.append(
                self.client.check(
                    ClientCheckRequest(
                        user=user,
                        relation=relation,
                        object=obj
                    )
                )
            )
        
        # Run all checks in parallel (Gather)
        # return_exceptions=True prevents one failure from crashing the whole UI response
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        
        permissions = {}
        for i, response in enumerate(responses):
            perm_name = keys[i]
            
            if isinstance(response, Exception):
                # Log error and fail safe (Deny Access)
                logger.error(f"FGA Check Failed | User: {user_id} | Perm: {perm_name} | Err: {response}")
                permissions[perm_name] = False
            else:
                # OpenFGA SDK returns allowed=True/False
                permissions[perm_name] = response.allowed
                
        return permissions

    async def has_permission(self, user: Union[int, Any], object_type: str, object_id: str, relation: str) -> bool:
        """
        Checks a single permission for a user.
        Useful for route guards (Dependencies).
        """
        try:
            # Handle both UserModel OR raw user_id (int/str)
            user_id = user.id if hasattr(user, "id") else user
            
            response = await self.client.check(
                ClientCheckRequest(
                    user=f"user:{user_id}",
                    relation=relation,
                    object=f"{object_type}:{object_id}"
                )
            )
            return response.allowed
        except Exception as e:
            logger.error(f"FGA Single Check Failed: {e}")
            return False