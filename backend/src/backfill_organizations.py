import asyncio
import logging
from sqlalchemy import select
from src.database import AsyncSessionLocal, get_connection
from src.users.user_model import User, UserModel
from src.workspaces.schema.workspace_model import Workspace, WorkspaceScopeEnum
from src.organizations.organization_model import Organization, OrganizationModel
from src.organizations.repository.organization_repository import OrganizationRepository
from src.organizations.organization_service import OrganizationService
from src.users.repository.user_repository import UserRepository

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Advisory Lock ID for backfill (arbitrary but consistent)
BACKFILL_LOCK_ID = 999

async def backfill_organizations():
    logger.info("Attempting to acquire advisory lock for backfill...")
    
    conn = None
    try:
        # Acquire advisory lock using raw connection
        conn = await get_connection()
        
        # Check if we can acquire the lock (wait if necessary)
        await conn.execute("SELECT pg_advisory_lock($1)", BACKFILL_LOCK_ID)
        logger.info("Advisory lock acquired. Starting backfill...")

        async with AsyncSessionLocal() as db:
            # 1. Initialize Repositories and Services
            user_repo = UserRepository(db)
            org_repo = OrganizationRepository(db)
            org_service = OrganizationService(org_repo)
            
            # 2. Fetch all users
            result = await db.execute(select(User))
            users = result.scalars().all()
            logger.info(f"Found {len(users)} users.")
            
            # 3. Ensure Organizations exist for all users
            user_org_map = {} # user_id -> { 'personal': Org, 'enterprise': Org }
            
            for user in users:
                logger.info(f"Ensuring orgs for user: {user.email}")
                
                # Convert SQLAlchemy User to Pydantic UserModel for service call
                # We need to ensure relationships are loaded or handle lazy loading if UserModel requires them
                # UserModel requires 'organizations' field which is a relationship.
                # If we didn't eager load it, accessing it might trigger query or fail if session is closed (but we are in session).
                # However, ensure_user_organization mainly needs email and name.
                # Let's create a minimal UserModel or try to map it.
                # Actually, ensure_user_organization returns an OrganizationModel.
                
                # We can construct UserModel manually to avoid validation issues with relationships
                user_model = UserModel(
                    id=user.id,
                    email=user.email,
                    name=user.name,
                    picture=user.picture,
                    roles=user.roles,
                    organizations=[] # We don't need existing orgs for this call, it checks DB
                )
                
                # This will create the orgs if they don't exist
                await org_service.ensure_user_organization(user_model)
                
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
        if conn:
            try:
                logger.info("Releasing advisory lock...")
                await conn.execute("SELECT pg_advisory_unlock($1)", BACKFILL_LOCK_ID)
                await conn.close()
                logger.info("Lock released.")
            except Exception as e:
                logger.error(f"Error releasing lock: {e}")

if __name__ == "__main__":
    asyncio.run(backfill_organizations())
