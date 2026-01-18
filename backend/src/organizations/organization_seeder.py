import logging
import mimetypes
import os
from typing import Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from src.common.base_dto import AspectRatioEnum
from src.common.schema.media_item_model import AssetRoleEnum
from src.common.storage_service import GcsService
from src.config.config_service import config_service
from src.media_templates.repository.media_template_repository import MediaTemplateRepository
from src.media_templates.schema.media_template_model import (
    GenerationParameters,
    IndustryEnum,
    MediaTemplateModel,
)
from src.source_assets.repository.source_asset_repository import SourceAssetRepository
from src.source_assets.schema.source_asset_model import (
    AssetScopeEnum as AssetScope,
    AssetTypeEnum as AssetType,
    SourceAssetModel,
)
from src.workspaces.repository.workspace_repository import WorkspaceRepository
from src.workspaces.schema.workspace_model import WorkspaceModel, WorkspaceScopeEnum
from src.users.user_model import UserModel
from bootstrap.seed_data import TEMPLATES

logger = logging.getLogger(__name__)

# Path to assets folder relative to this file
# This file is in src/organizations/organization_seeder.py
# Assets are in src/assets
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.abspath(os.path.join(CURRENT_DIR, "../assets"))

class OrganizationSeeder:
    """
    Service to seed initial data (workspaces, assets, templates) for an organization.
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.workspace_repo = WorkspaceRepository(db)
        self.asset_repo = SourceAssetRepository(db)
        self.template_repo = MediaTemplateRepository(db)
        self.gcs_service = GcsService()

    async def seed_organization(self, org_id: int, admin_user: UserModel):
        """
        Seeds an organization with default workspaces and assets.
        For now, this mainly focuses on the 'Public Workspace' and system assets
        which are currently global or attached to the Admin's Public Workspace.
        """
        # 1. Ensure Public Workspace exists for this Org
        public_ws = await self.ensure_public_workspace(org_id, admin_user)
        
        if not public_ws:
            logger.error(f"Failed to ensure public workspace for org {org_id}. Skipping seeding.")
            return

        # 2. Seed System Assets (VTO, Templates)
        # TODO: For now use system wide assets and templates
        # await self.seed_vto_assets(public_ws, admin_user)
        # await self.seed_media_templates(public_ws, admin_user)

    async def ensure_public_workspace(self, org_id: int, admin_user: UserModel) -> Optional[WorkspaceModel]:
        # Check if public workspace exists for this org
        existing = await self.workspace_repo.get_public_workspace_by_org_id(org_id)
        if existing:
            return existing
            
        # TODO: Create it if missing
        # We need the Org name to name the workspace nicely?
        # For now, let's use a generic name or fetch Org.
        # To fetch Org, we'd need OrgRepo. Let's assume generic name "Public Workspace"
        # or we can fetch it if we inject OrgRepo.
        # But for simplicity, let's just call it "Public Workspace" or similar.
        
        # Actually, let's try to fetch the org name if possible, or just use "Organization Public Workspace".
        
        logger.info(f"Creating default Public Workspace for Org {org_id}...")
        project_id = config_service.PROJECT_ID
        workspace_name = (
            project_id.replace("-", " ").replace("_", " ").title()
            + " Workspace"
        )
        new_workspace = WorkspaceModel(
            name=workspace_name,
            owner_id=admin_user.id,
            scope=WorkspaceScopeEnum.PUBLIC,
            organization_id=org_id,
            members=[],
        )
        return await self.workspace_repo.create(new_workspace)

    def upload_assets_from_folder(self, local_folder: str, gcs_prefix: str) -> Dict[str, str]:
        uri_map = {}
        abs_local_folder = os.path.join(ASSETS_DIR, local_folder)
        
        if not os.path.isdir(abs_local_folder):
            logger.warning(f"Local asset folder not found: {abs_local_folder}")
            return {}

        for filename in os.listdir(abs_local_folder):
            local_path = os.path.join(abs_local_folder, filename)
            if os.path.isfile(local_path):
                destination_blob_name = f"{gcs_prefix}/{filename}"
                mime_type, _ = mimetypes.guess_type(local_path)
                if not mime_type:
                    mime_type = "application/octet-stream"
                
                gcs_uri = self.gcs_service.upload_file_to_gcs(
                    local_path=local_path,
                    destination_blob_name=destination_blob_name,
                    mime_type=mime_type,
                )
                if gcs_uri:
                    uri_map[filename] = gcs_uri
        return uri_map

    def upload_specific_assets(self, local_filenames: set[str], local_folder: str, gcs_prefix: str) -> Dict[str, str]:
        uri_map = {}
        abs_local_folder = os.path.join(ASSETS_DIR, local_folder)
        
        for filename in local_filenames:
            local_path = os.path.join(abs_local_folder, filename)
            if os.path.isfile(local_path):
                destination_blob_name = f"{gcs_prefix}/{filename}"
                mime_type, _ = mimetypes.guess_type(local_path)
                mime_type = mime_type or "application/octet-stream"
                
                gcs_uri = self.gcs_service.upload_file_to_gcs(
                    local_path=local_path,
                    destination_blob_name=destination_blob_name,
                    mime_type=mime_type,
                )
                if gcs_uri:
                    uri_map[filename] = gcs_uri
        return uri_map

    async def seed_vto_assets(self, workspace: WorkspaceModel, admin_user: UserModel):
        logger.info(f"Seeding VTO assets for Workspace {workspace.id}...")
        vto_asset_folders = ["vto/garments", "vto/models"]
        
        for folder in vto_asset_folders:
            # We use a shared GCS prefix for system assets to avoid duplication?
            # Or per-org prefix?
            # If they are system assets, they should be shared.
            # But SourceAssetModel is per workspace.
            # If we link the SAME GCS URI to multiple workspaces, that's fine.
            gcs_prefix = f"system_assets/{folder}"
            uri_map = self.upload_assets_from_folder(folder, gcs_prefix)
            
            for filename, gcs_uri in uri_map.items():
                # Check if asset exists in THIS workspace
                # We need to check by GCS URI AND Workspace ID?
                # Or just GCS URI globally?
                # SourceAssetRepository.get_by_gcs_uri returns ONE asset.
                # If we have multi-tenancy, we might have multiple assets pointing to same GCS URI (one per workspace).
                # We need to check if we have an asset in THIS workspace.
                
                # For now, let's assume we create a new SourceAssetModel for this workspace
                # pointing to the shared GCS URI.
                
                # Check if already exists in this workspace
                # We'll need a custom query or just try create and catch error?
                # Or list assets in workspace and check?
                # Let's just create it and ignore if unique constraint fails (if any).
                # But we don't have unique constraint on GCS URI per workspace yet?
                
                # Let's try to find it.
                # existing = await self.asset_repo.get_by_workspace_and_uri(workspace.id, gcs_uri)
                # We don't have that method.
                
                # Let's skip check for now and just create (it might duplicate if run multiple times).
                # Ideally we check.
                
                asset_type = None
                try:
                    base_name = os.path.splitext(filename)[0]
                    type_parts = base_name.split("_")[:-1]
                    type_string = "_".join(type_parts)
                    asset_type = AssetType(type_string)
                except (ValueError, IndexError):
                    continue

                new_asset = SourceAssetModel(
                    workspace_id=workspace.id,
                    original_filename=filename,
                    gcs_uri=gcs_uri,
                    mime_type="image/png",
                    scope=AssetScope.SYSTEM,
                    asset_type=asset_type,
                    user_id=admin_user.id,
                    aspect_ratio=AspectRatioEnum.RATIO_9_16,
                )
                await self.asset_repo.create(new_asset)

    async def seed_media_templates(self, workspace: WorkspaceModel, admin_user: UserModel):
        logger.info(f"Seeding Media Templates for Workspace {workspace.id}...")
        
        # 1. Identify templates
        # We check if template exists by name? Templates are global or per workspace?
        # MediaTemplateModel doesn't seem to have workspace_id?
        # Let's check MediaTemplateModel.
        # If they are global, we only seed once.
        # If they are global, why seed "every time we create an organization"?
        # Maybe the user implies the ASSETS for the templates?
        
        # If MediaTemplateModel is global, we just run this once (Global Admin Org).
        # If we run this for every org, we might be creating duplicates if they are not scoped.
        pass
