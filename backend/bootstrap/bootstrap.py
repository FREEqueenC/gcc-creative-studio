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

from src.config.config_service import config_service
from src.database import AsyncSessionLocal, cleanup_connector
from src.users.dto.user_create_dto import UserCreateDto
from src.users.repository.user_repository import UserRepository
from src.users.user_model import UserModel
from src.organizations.organization_seeder import OrganizationSeeder
from src.organizations.organization_service import OrganizationService
from src.organizations.repository.organization_repository import OrganizationRepository
from src.backfill_organizations import backfill_organizations

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


async def main():
    try:
        # Run Database Migrations before seeding
        from src.database_migrations import run_pending_migrations
        await run_pending_migrations()

        async with AsyncSessionLocal() as db:
            admin_user = await ensure_admin_user_exists(db)
            
            if admin_user:
                # Ensure Admin Org exists and seed it
                org_repo = OrganizationRepository(db)
                org_service = OrganizationService(org_repo)
                
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
                
                admin_org = await org_service.ensure_user_organization(admin_user_model)
                logger.info(f"Seeding data for Admin Organization: {admin_org.name}")
                
                seeder = OrganizationSeeder(db)
                await seeder.seed_organization(admin_org.id, admin_user)
            else:
                logger.warning("No admin user found. Skipping organization seeding.")

        # Run Backfill Logic (Users, Workspaces, FGA)
        logger.info("--- Running Organization Backfill ---")
        await backfill_organizations()

    finally:
        await cleanup_connector()


if __name__ == "__main__":
    asyncio.run(main())
