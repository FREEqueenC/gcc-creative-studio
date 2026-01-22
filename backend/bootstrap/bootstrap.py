# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import asyncio
import logging
import os
from typing import Optional

# --- Setup Logging Globally First ---
from src.config.logger_config import setup_logging

setup_logging()

from typing import Dict, List
import mimetypes

from src.config.config_service import config_service
from src.database import AsyncSessionLocal, cleanup_connector
from src.users.dto.user_create_dto import UserCreateDto
from src.users.repository.user_repository import UserRepository
from src.users.user_model import UserModel
from src.organizations.organization_service import OrganizationService
from src.organizations.repository.organization_repository import OrganizationRepository
from src.backfill_organizations import backfill_organizations
from src.common.base_dto import AspectRatioEnum
from src.common.storage_service import GcsService
from src.media_templates.repository.media_template_repository import MediaTemplateRepository
from src.source_assets.repository.source_asset_repository import SourceAssetRepository
from src.workspaces.repository.workspace_repository import WorkspaceRepository
from src.common.schema.media_item_model import AssetRoleEnum
from src.source_assets.schema.source_asset_model import SourceAssetModel, AssetScopeEnum, AssetTypeEnum
from src.common.email_service import EmailService
from src.common.consistency_service import ConsistencyService
from src.media_templates.schema.media_template_model import MediaTemplateModel, GenerationParameters, IndustryEnum
from src.workspaces.workspace_service import WorkspaceService
from src.core.fga import fga_client, config as fga_config
from openfga_sdk import OpenFgaClient
from src.core.fga_setup import setup_fga

# Placeholder for TEMPLATES if not defined elsewhere
TEMPLATES: List[Dict] = []

logger = logging.getLogger(__name__)

# Get the absolute path of the directory where this script is located.
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def get_admin_email() -> str:
    return config_service.ADMIN_USER_EMAIL


async def ensure_admin_user_exists(db: AsyncSessionLocal) -> Optional[UserModel]:
    """
    Ensures a user document exists for the admin running the script.
    Returns the admin user model.
    """
    logger.info("--- Ensuring Admin User Exists ---")
    admin_email = get_admin_email()

    if admin_email == "system":
        logger.info(
            "Bootstrap running as 'system'. Skipping admin user creation."
        )
        return None

    try:
        logger.info(f"Looking up user for email: {admin_email}")
        user_repo = UserRepository(db)
        existing_user = await user_repo.get_by_email(admin_email)

        if existing_user:
            logger.info(f"User document for '{admin_email}' already exists. ID: {existing_user.id}")
            return existing_user
        else:
            logger.warning(
                f"No user document found for email '{admin_email}'. Creating one."
            )
            name = admin_email.split("@")[0]
            logger.info(f"Setting user's default name to '{name}'.")

            new_user_dto = UserCreateDto(
                email=admin_email,
                name=name,
            )
            user_data = new_user_dto.model_dump()
            created_user = await user_repo.create(user_data)
            logger.info(
                f"Successfully created admin user document for '{admin_email}'. ID: {created_user.id}"
            )

            # Grant Super Admin permission in OpenFGA
            try:
                from src.core.fga import fga_client
                from openfga_sdk.client.models import ClientWriteRequest, ClientTuple

                logger.info(f"Granting super_admin permission to user {created_user.id} in OpenFGA...")
                await fga_client.write(
                    ClientWriteRequest(
                        writes=[
                            ClientTuple(
                                user=f"user:{created_user.id}",
                                relation="super_admin",
                                object="platform:creative-studio",
                            )
                        ]
                    )
                )
                logger.info("Successfully granted super_admin permission.")
            except Exception as e:
                logger.error(f"Failed to grant super_admin permission in OpenFGA: {e}")

            return created_user

    except Exception as e:
        logger.error(
            f"Failed to create or verify admin user for '{admin_email}': {e}",
            exc_info=True,
        )
        return None

def upload_assets_from_folder(
    local_folder: str, gcs_prefix: str
) -> Dict[str, str]:
    """
    Uploads all files from a local folder to a GCS path and returns a mapping.
    """
    gcs_service = GcsService()
    uri_map = {}
    logger.info(f"Uploading assets from '{local_folder}' to GCS...")

    # Construct an absolute path to the assets folder
    abs_local_folder = os.path.join(SCRIPT_DIR, "assets", local_folder)
    logger.info(
        f"Uploading assets from '{abs_local_folder}' to GCS prefix '{gcs_prefix}'..."
    )

    if not os.path.isdir(abs_local_folder):
        logger.warning(f"Local asset folder not found: {abs_local_folder}")
        return {}

    for filename in os.listdir(abs_local_folder):
        local_path = os.path.join(abs_local_folder, filename)

        if os.path.isfile(local_path):
            destination_blob_name = f"{gcs_prefix}/{filename}"
            mime_type, _ = mimetypes.guess_type(local_path)
            # Provide a default mime_type if it cannot be guessed
            if not mime_type:
                mime_type = "application/octet-stream"
            gcs_uri = gcs_service.upload_file_to_gcs(  # type: ignore
                local_path=local_path,
                destination_blob_name=destination_blob_name,
                mime_type=mime_type,
            )
            if gcs_uri:
                uri_map[filename] = gcs_uri
                logger.info(f"  - Uploaded {filename} to {gcs_uri}")
    return uri_map


def upload_specific_assets(
    local_filenames: set[str], local_folder: str, gcs_prefix: str
) -> Dict[str, str]:
    """
    Uploads a specific list of files from a local folder to a GCS path.
    """
    gcs_service = GcsService()
    uri_map = {}
    logger.info(
        f"Uploading {len(local_filenames)} specific assets from '{local_folder}' to GCS..."
    )

    abs_local_folder = os.path.join(SCRIPT_DIR, "assets", local_folder)

    for filename in local_filenames:
        local_path = os.path.join(abs_local_folder, filename)
        if os.path.isfile(local_path):
            destination_blob_name = f"{gcs_prefix}/{filename}"
            mime_type, _ = mimetypes.guess_type(local_path)
            mime_type = mime_type or "application/octet-stream"

            gcs_uri = gcs_service.upload_file_to_gcs(  # type: ignore
                local_path=local_path,
                destination_blob_name=destination_blob_name,
                mime_type=mime_type,
            )
            if gcs_uri:
                uri_map[filename] = gcs_uri
                logger.info(f"  - Uploaded {filename} to {gcs_uri}")
    return uri_map


async def seed_media_templates(db: AsyncSessionLocal, admin_user: Optional[UserModel]):
    """
    Uploads media template assets and seeds the media_templates collection.
    """
    logger.info("--- Starting Media Template Seeding ---")
    template_repo = MediaTemplateRepository(db)
    asset_repo = SourceAssetRepository(db)
    workspace_repo = WorkspaceRepository(db)

    if not admin_user:
        logger.error("Cannot seed media templates without an admin user.")
        return

    # 1. Identify which templates need to be created
    templates_to_create = []
    for template_data in TEMPLATES:
        template_name = template_data["name"]
        existing = await template_repo.get_by_name(template_name)
        if existing:
            logger.info(f"Template '{template_name}' already exists. Skipping.")
        else:
            templates_to_create.append(template_data)

    if not templates_to_create:
        logger.info("All media templates are already seeded. Nothing to do.")
        return

    # 2. Collect all unique asset filenames needed for the new templates
    required_filenames = set()
    for template_data in templates_to_create:
        required_filenames.update(template_data.get("local_uris", []))
        required_filenames.update(template_data.get("local_thumbnail_uris", []))
        for asset_info in template_data.get("input_gcs_uris", []):
            if "local_uri" in asset_info:
                required_filenames.add(asset_info["local_uri"])

    # 3. Upload only the required assets
    # Note: GCS upload is synchronous
    uri_map = upload_specific_assets(
        required_filenames, "media-template", "media_template_assets"
    )

    # 4. Iterate through the new templates and create documents
    for template_data in templates_to_create:
        template_name = template_data["name"]
        logger.info(f"Processing template: '{template_name}'")

        # Map local URIs to GCS URIs and create system assets
        gcs_uris = [
            uri
            for local_uri in template_data.get("local_uris", [])
            if (uri := uri_map.get(local_uri)) is not None
        ]

        thumbnail_gcs_uris = [
            uri
            for local_uri in template_data.get("local_thumbnail_uris", [])
            if (uri := uri_map.get(local_uri)) is not None
        ]

        if not gcs_uris and template_data.get("local_uris"):
            logger.warning(
                f"  - No assets found/uploaded for template '{template_name}'. Skipping."
            )
            continue

        public_workspace = await workspace_repo.get_public_workspace()
        if not public_workspace:
            logger.error(
                "Public workspace not found. Cannot create system assets for templates."
            )
            return

        new_source_asset_links = []
        # We only care about the first GCS URI as the main media.
        # The rest are considered input assets for generation.
        main_gcs_uri = gcs_uris[0] if gcs_uris else None
        input_assets_data = template_data.get("input_gcs_uris", [])

        for asset_data in input_assets_data:
            local_uri = asset_data.get("local_uri")
            mime_type = asset_data.get("mime_type")
            role = asset_data.get(
                "role", AssetRoleEnum.INPUT
            )  # Default to INPUT

            if not local_uri or not mime_type:
                logger.warning(
                    f"  - Skipping invalid input asset data in '{template_name}': {asset_data}"
                )
                continue

            gcs_uri = uri_map.get(local_uri)
            if not gcs_uri:
                logger.warning(
                    f"  - GCS URI not found for local file '{local_uri}'."
                )
                continue

            asset_id_to_link: int | None = None
            existing_asset = await asset_repo.get_by_gcs_uri(gcs_uri)

            if existing_asset:
                # If asset already exists, get its ID to link it.
                asset_id_to_link = existing_asset.id
                logger.info(
                    f"  - Found existing asset for '{local_uri}'. Re-using ID: {asset_id_to_link}"
                )
            else:
                # If asset does not exist, create it and get the new ID.
                new_asset = SourceAssetModel(
                    workspace_id=public_workspace.id,
                    original_filename=local_uri,
                    gcs_uri=gcs_uri,
                    mime_type=mime_type,
                    scope=AssetScopeEnum.SYSTEM,
                    asset_type=AssetTypeEnum.GENERIC_IMAGE,  # Default type for templates
                    user_id=admin_user.id,
                    file_hash="",  # Not strictly needed for system assets
                )
                created_asset = await asset_repo.create(new_asset)
                asset_id_to_link = created_asset.id

            if asset_id_to_link:
                new_source_asset_links.append(
                    {"asset_id": asset_id_to_link, "role": role}
                )

        # Create the Pydantic models
        gen_params = GenerationParameters(
            **template_data["generation_parameters"]
        )
        # ID is auto-generated by DB, so we don't pass 'id' from template_data unless we want to force it (not recommended for Serial)
        # But template_data has "id" (string). We should probably ignore it or use it as name/slug if needed.
        # For now, we ignore the string ID from seed data and let DB generate int ID.
        
        new_template = MediaTemplateModel(
            name=template_name,
            description=template_data["description"],
            mime_type=template_data["mime_type"],
            industry=(
                IndustryEnum(template_data["industry"])
                if template_data.get("industry")
                else None
            ),
            brand=template_data.get("brand"),
            tags=template_data.get("tags", []),
            gcs_uris=[main_gcs_uri] if main_gcs_uri else [],
            thumbnail_uris=thumbnail_gcs_uris,
            source_assets=new_source_asset_links or None,
            generation_parameters=gen_params,
        )

        await template_repo.create(new_template)
        logger.info(f"  - Successfully saved template '{template_name}'.")


async def seed_vto_assets(db: AsyncSessionLocal, admin_user: Optional[UserModel]):
    """
    Uploads system-level VTO assets (garments, models) for the VTO feature.
    """
    logger.info("--- Starting VTO System Asset Seeding ---")
    asset_repo = SourceAssetRepository(db)
    workspace_repo = WorkspaceRepository(db)
    public_workspace = await workspace_repo.get_public_workspace()

    if not public_workspace:
        logger.error("Cannot seed VTO assets: Public workspace not found.")
        return

    if not admin_user:
        logger.error("Cannot seed VTO assets without an admin user.")
        return

    vto_asset_folders = ["vto/garments", "vto/models"]

    for folder in vto_asset_folders:
        local_folder = folder
        gcs_prefix = f"system_assets/{folder}"
        mime_type = "image/png"  # Assuming all VTO assets are PNGs

        uri_map = upload_assets_from_folder(local_folder, gcs_prefix)

        for filename, gcs_uri in uri_map.items():
            # Check if an asset with this GCS URI already exists
            existing = await asset_repo.get_by_gcs_uri(gcs_uri)
            if existing:
                logger.info(
                    f"VTO asset for '{gcs_uri}' already exists. Skipping."
                )
                continue

            # --- Dynamically determine asset type from filename convention ---
            asset_type = None
            try:
                # Get filename without extension, e.g., "vto_top_0"
                base_name = os.path.splitext(filename)[0]
                # Split by underscore and remove the last part (the index)
                type_parts = base_name.split("_")[:-1]
                # Join the remaining parts to get the type string, e.g., "vto_top"
                type_string = "_".join(type_parts)
                # Convert the string to an AssetType enum member
                asset_type = AssetTypeEnum(type_string)
                logger.info(
                    f"  - Detected asset type as '{asset_type.value}' for {filename}"
                )
            except (ValueError, IndexError):
                logger.warning(
                    f"  - Could not determine asset type for '{filename}' from its name. Skipping."
                )
                continue

            logger.info(f"Creating VTO asset for: {filename}")
            new_asset = SourceAssetModel(
                workspace_id=public_workspace.id,
                original_filename=filename,
                gcs_uri=gcs_uri,
                mime_type=mime_type,  # type: ignore
                file_hash="",  # Not strictly needed for system assets
                scope=AssetScopeEnum.SYSTEM,
                asset_type=asset_type,
                user_id=admin_user.id,
                aspect_ratio=AspectRatioEnum.RATIO_9_16,
            )
            await asset_repo.create(new_asset)
            logger.info(f"  - Successfully saved VTO asset '{filename}'.")

async def main():
    try:
        # Run Database Migrations before seeding
        from src.database_migrations import run_pending_migrations
        await run_pending_migrations()

        async with AsyncSessionLocal() as db:
            # Initialize OpenFGA
            try:
                logger.info("Initializing OpenFGA...")
                real_fga_client = OpenFgaClient(fga_config)
                fga_client.set_client(real_fga_client)
                await setup_fga(real_fga_client)
            except Exception as e:
                logger.error(f"Failed to initialize OpenFGA: {e}")
                # We should probably fail here as FGA is critical for workspace creation
                raise e

            admin_user = await ensure_admin_user_exists(db)
            
            if admin_user:
                # Ensure Admin Org exists and seed it
                org_repo = OrganizationRepository(db)
                org_service = OrganizationService(org_repo)
                
                # Instantiate dependencies for WorkspaceService
                workspace_repo = WorkspaceRepository(db)
                user_repo = UserRepository(db)
                email_service = EmailService()
                consistency_service = ConsistencyService()
                
                workspace_service = WorkspaceService(
                    workspace_repo=workspace_repo,
                    user_repo=user_repo,
                    email_service=email_service,
                    organization_service=org_service,
                    consistency_service=consistency_service
                )
                
                # We need to ensure the admin has an organization to seed
                # This logic is similar to backfill but for initial bootstrap
                # We'll rely on ensure_user_organization to get/create the primary org
                # But we need a UserModel with roles/orgs for the service call
                # We can construct a minimal one
                admin_user_model = UserModel(
                    id=admin_user.id,
                    email=admin_user.email,
                    name=admin_user.name,
                    picture=admin_user.picture,
                    roles=admin_user.roles,
                    organizations=[]
                )
                
                # Ensure user belongs to an organization (Personal or Enterprise)
                admin_org = await org_service.ensure_user_organization(admin_user_model)
                
                # Ensure default workspaces exist (Personal + Public for Enterprise)
                await workspace_service.ensure_default_workspaces(admin_user_model, admin_org)
                
                # Seed System Data (Assets, Templates)
                await seed_vto_assets(db, admin_user)
                await seed_media_templates(db, admin_user)
            else:
                logger.warning("No admin user found. Skipping organization seeding.")

        # Run Backfill Logic (Users, Workspaces, FGA)
        logger.info("--- Running Organization Backfill ---")
        await backfill_organizations()

    finally:
        await cleanup_connector()


if __name__ == "__main__":
    asyncio.run(main())
