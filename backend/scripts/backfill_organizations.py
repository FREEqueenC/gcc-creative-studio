import asyncio
import os
import sys
import logging

# Add the parent directory to sys.path to allow imports from src
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import AsyncSessionLocal, get_connection
from src.users.user_model import UserModel
from src.workspaces.schema.workspace_model import Workspace, WorkspaceScopeEnum
from src.organizations.organization_model import OrganizationModel
from src.organizations.repository.organization_repository import OrganizationRepository
from src.organizations.organization_service import OrganizationService
from src.users.repository.user_repository import UserRepository

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Advisory Lock ID (arbitrary but consistent)
BACKFILL_LOCK_ID = 999

async def backfill_organizations():
    logger.info("Attempting to acquire advisory lock for backfill...")
    
    # Acquire advisory lock using raw connection
    conn = await get_connection()
    try:
        # Check if we can acquire the lock (wait if necessary)
        # Using session-level advisory lock
        await conn.execute("SELECT pg_advisory_lock($1)", BACKFILL_LOCK_ID)
        logger.info("Advisory lock acquired. Starting backfill...")

        async with AsyncSessionLocal() as db:
            # 1. Initialize Repositories and Services
            user_repo = UserRepository(db)
            org_repo = OrganizationRepository(db)
            org_service = OrganizationService(org_repo)
            
            # 2. Fetch all users
            result = await db.execute(select(UserModel))
            users = result.scalars().all()
            logger.info(f"Found {len(users)} users.")
            
            # 3. Ensure Organizations exist for all users
            user_org_map = {} # user_id -> { 'personal': Org, 'enterprise': Org }
            
            for user in users:
                logger.info(f"Ensuring orgs for user: {user.email}")
                # This will create the orgs if they don't exist
                await org_service.ensure_user_organization(user)
                
                # Now fetch them to have them in memory
                orgs = await org_service.get_user_organizations(user.id)
                
                personal = next((o for o in orgs if o.domain is None), None)
                enterprise = next((o for o in orgs if o.domain is not None), None)
                
                user_org_map[user.id] = {
                    'personal': personal,
                    'enterprise': enterprise
                }
                
            # 4. Fetch Workspaces without Organization
            result = await db.execute(select(Workspace).where(Workspace.organization_id == None))
            workspaces = result.scalars().all()
            logger.info(f"Found {len(workspaces)} workspaces to backfill.")
            
            for ws in workspaces:
                owner_orgs = user_org_map.get(ws.owner_id)
                if not owner_orgs:
                    logger.warning(f"Skipping workspace {ws.name} (ID: {ws.id}) - Owner {ws.owner_id} not found.")
                    continue
                    
                target_org = None
                
                # Logic:
                # Public -> Enterprise (if exists), else Personal
                # Private -> Personal
                
                if ws.scope == WorkspaceScopeEnum.PUBLIC.value:
                    if owner_orgs['enterprise']:
                        target_org = owner_orgs['enterprise']
                        logger.info(f"Assigning PUBLIC workspace '{ws.name}' to Enterprise Org: {target_org.name}")
                    else:
                        target_org = owner_orgs['personal']
                        logger.info(f"Assigning PUBLIC workspace '{ws.name}' to Personal Org: {target_org.name} (No Enterprise Org found)")
                else:
                    # Private -> Personal
                    target_org = owner_orgs['personal']
                    # Fallback if for some reason personal org creation failed (unlikely)
                    if not target_org and owner_orgs['enterprise']:
                         target_org = owner_orgs['enterprise']
                    
                    logger.info(f"Assigning PRIVATE workspace '{ws.name}' to Personal Org: {target_org.name if target_org else 'None'}")

                if target_org:
                    ws.organization_id = target_org.id
                    db.add(ws)
                else:
                    logger.error(f"Could not determine target org for workspace {ws.id}")

            await db.commit()
            logger.info("Backfill completed successfully!")

    except Exception as e:
        logger.error(f"An error occurred during backfill: {e}")
        raise
    finally:
        # Release the lock
        logger.info("Releasing advisory lock...")
        await conn.execute("SELECT pg_advisory_unlock($1)", BACKFILL_LOCK_ID)
        await conn.close()
        logger.info("Lock released.")

if __name__ == "__main__":
    asyncio.run(backfill_organizations())
