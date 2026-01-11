import asyncio
from typing import List, Dict, Any, Type, TypeVar
from openfga_sdk import OpenFgaClient
from openfga_sdk.client.models import ClientCheckRequest
from src.core.fga import fga_client

T = TypeVar("T")

class PermissionService:
    """
    Service to efficiently calculate permissions for resources using OpenFGA.
    """

    def __init__(self, client: OpenFgaClient = None):
        self.client = client or fga_client

    async def get_permissions_for_workspace(self, user_id: int, workspace_id: int) -> Dict[str, bool]:
        """
        Calculates permissions for a single workspace.
        """
        checks = {
            "can_manage_members": "admin",
            "can_edit": "editor",
            "can_delete": "admin",
            "can_view_workflows": "can_view_workflows",
            "can_manage_workflows": "can_manage_workflows",
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
            "can_manage_members": "admin",
            "can_edit": "admin", # Org editing usually requires admin
            "can_delete": "admin",
            "is_admin": "admin",
        }
        
        results = await self._batch_check(user_id, "organization", str(org_id), checks)
        return results

    async def _batch_check(self, user_id: int, object_type: str, object_id: str, checks: Dict[str, str]) -> Dict[str, bool]:
        """
        Performs parallel FGA checks.
        checks: Dict mapping 'permission_name' -> 'fga_relation'
        """
        user = f"user:{user_id}"
        obj = f"{object_type}:{object_id}"
        
        # Create coroutines for all checks
        tasks = []
        keys = []
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
        
        # Run all checks in parallel
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        
        permissions = {}
        for i, response in enumerate(responses):
            perm_name = keys[i]
            if isinstance(response, Exception):
                # Log error and default to False
                # logger.error(f"FGA check failed for {perm_name}: {response}")
                permissions[perm_name] = False
            else:
                permissions[perm_name] = response.allowed
                
        return permissions
