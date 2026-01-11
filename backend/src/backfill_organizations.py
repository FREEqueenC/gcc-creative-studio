import asyncio
import logging
from sqlalchemy import select
from src.database import AsyncSessionLocal, get_connection
from src.users.user_model import User, UserModel
from src.workspaces.schema.workspace_model import Workspace, WorkspaceScopeEnum, WorkspaceRoleEnum, WorkspaceMemberAssociation
from src.organizations.organization_model import Organization, OrganizationModel
from src.organizations.repository.organization_repository import OrganizationRepository
from src.organizations.organization_service import OrganizationService, GENERIC_DOMAINS
from src.users.repository.user_repository import UserRepository
from src.workspaces.repository.workspace_repository import WorkspaceRepository
from src.organizations.organization_model import UserOrganization

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
            workspace_repo = WorkspaceRepository(db)
            
            # 2. Fetch all users
            result = await db.execute(select(User))
            users = result.scalars().all()
            logger.info(f"Found {len(users)} users.")
            
            # 3. Identify Admin Organization (The "Default" Org)
            admin_user = None
            for user in users:
                roles = user.roles or []
                if "admin" in [r.lower() for r in roles] or getattr(user, 'is_super_admin', False):
                    admin_user = user
                    break
            
            admin_org = None
            if admin_user:
                logger.info(f"Identified Admin User: {admin_user.email}")
                # Ensure Admin has their primary org
                admin_user_model = UserModel(
                    id=admin_user.id,
                    email=admin_user.email,
                    name=admin_user.name,
                    picture=admin_user.picture,
                    roles=admin_user.roles,
                    organizations=[]
                )
                # This returns their Primary Org (Enterprise or Personal)
                admin_primary_org = await org_service.ensure_user_organization(admin_user_model)
                
                # We prefer an Enterprise Org as the "Default Admin Org" if available
                # If the admin has a generic email, their primary is Personal.
                # If they have an enterprise email, it's Enterprise.
                admin_org = admin_primary_org
                
                # If for some reason it's None (shouldn't be), create default
                if not admin_org:
                     admin_org = await org_repo.create(OrganizationModel(
                        name="Default Organization",
                        owner_id=admin_user.id,
                        domain="default"
                    ))
            else:
                logger.warning("No Admin User found! Creating a system default organization.")
                # Fallback if no users at all or no admin
                # This might fail if no users exist to be owner.
                if users:
                     admin_org = await org_repo.create(OrganizationModel(
                        name="Default Organization",
                        owner_id=users[0].id,
                        domain="default"
                    ))
            
            if admin_org:
                logger.info(f"Using Organization '{admin_org.name}' (ID: {admin_org.id}) as the Default/Admin Organization.")

            # 4. Process Each User
            user_primary_org_map = {} # user_id -> OrganizationModel
            
            for user in users:
                logger.info(f"Processing user: {user.email}")
                
                user_model = UserModel(
                    id=user.id,
                    email=user.email,
                    name=user.name,
                    picture=user.picture,
                    roles=user.roles,
                    organizations=[]
                )
                
                # 4.1 Ensure Primary Organization (Personal or Enterprise)
                primary_org = await org_service.ensure_user_organization(user_model)
                user_primary_org_map[user.id] = primary_org
                
                # 4.2 Ensure Personal Workspace in Primary Org
                # Check if exists
                user_workspaces = await workspace_repo.find_by_member_id(user.id)
                personal_ws = next(
                    (w for w in user_workspaces if w.organization_id == primary_org.id and w.scope == WorkspaceScopeEnum.PRIVATE and w.owner_id == user.id),
                    None
                )
                
                if not personal_ws:
                    logger.info(f"Creating Personal Workspace for {user.email} in Org {primary_org.name}")
                    ws_name = f"{user.name}'s Workspace" if user.name else "My Workspace"
                    new_ws = Workspace(
                        name=ws_name,
                        owner_id=user.id,
                        organization_id=primary_org.id,
                        scope=WorkspaceScopeEnum.PRIVATE.value
                    )
                    # Add owner as member
                    member = WorkspaceMemberAssociation(
                        user_id=user.id,
                        role=WorkspaceRoleEnum.OWNER
                    )
                    new_ws.members.append(member)
                    db.add(new_ws)
                    await db.flush() # To get ID
                
                # 4.3 Add User to Admin Org (if different from Primary)
                # This ensures everyone is in the "Default" org to see public stuff
                if admin_org and primary_org.id != admin_org.id:
                    # Check if link exists
                    stmt = select(UserOrganization).where(
                        UserOrganization.user_id == user.id,
                        UserOrganization.organization_id == admin_org.id
                    )
                    link = (await db.execute(stmt)).scalar_one_or_none()
                    
                    if not link:
                        logger.info(f"Adding {user.email} to Admin Org {admin_org.name}")
                        new_link = UserOrganization(
                            user_id=user.id,
                            organization_id=admin_org.id,
                            role="member"
                        )
                        db.add(new_link)

            # 5. Migrate Workspaces (Assign to correct Orgs)
            result = await db.execute(select(Workspace))
            all_workspaces = result.scalars().all()
            
            for ws in all_workspaces:
                target_org_id = None
                
                if ws.scope == WorkspaceScopeEnum.PUBLIC.value:
                    # Public workspaces go to Admin Org (The "Company" Org)
                    if admin_org:
                        target_org_id = admin_org.id
                else:
                    # Private workspaces go to the Owner's Primary Org
                    owner_primary = user_primary_org_map.get(ws.owner_id)
                    if owner_primary:
                        target_org_id = owner_primary.id
                
                if target_org_id and ws.organization_id != target_org_id:
                    logger.info(f"Moving Workspace '{ws.name}' (ID: {ws.id}) to Org ID: {target_org_id}")
                    ws.organization_id = target_org_id
                    db.add(ws)

            # 6. OpenFGA Backfill
            logger.info("Starting OpenFGA Permission Backfill...")
            
            from src.core.fga import fga_client, config as fga_config
            from openfga_sdk import OpenFgaClient
            from src.core.fga_setup import setup_fga
            from openfga_sdk.client.models import ClientWriteRequest, ClientTuple

            real_fga_client = OpenFgaClient(fga_config)
            fga_client.set_client(real_fga_client)
            await setup_fga(real_fga_client)
            
            writes = []
            
            # 6.1 Platform Super Admins
            for user in users:
                roles = user.roles or []
                if "admin" in [r.lower() for r in roles]:
                    writes.append(ClientTuple(
                        user=f"user:{user.id}",
                        relation="super_admin",
                        object="platform:creative-studio"
                    ))

            # 6.2 Organization Memberships
            # Re-fetch all UserOrganization links
            result = await db.execute(select(UserOrganization))
            user_org_links = result.scalars().all()
            
            for link in user_org_links:
                relation = "admin" if link.role == "admin" or link.role == "owner" else "member"
                writes.append(ClientTuple(
                    user=f"user:{link.user_id}",
                    relation=relation,
                    object=f"organization:{link.organization_id}"
                ))

            # 6.3 Workspace Permissions
            # Fetch all workspaces again (some might have been updated)
            result = await db.execute(select(Workspace))
            workspaces_final = result.scalars().all()
            
            for ws in workspaces_final:
                # Parent Org relationship
                if ws.organization_id is not None:
                    writes.append(ClientTuple(
                        user=f"organization:{ws.organization_id}",
                        relation="parent",
                        object=f"workspace:{ws.id}"
                    ))
                
                # Members
                for member in ws.members:
                    fga_role = member.role.value if hasattr(member.role, 'value') else member.role
                    relation = "viewer"
                    if fga_role == "editor":
                        relation = "editor"
                    elif fga_role == "admin":
                        relation = "admin"
                    elif fga_role == "owner":
                        # Map owner to admin since 'owner' relation doesn't exist in FGA model yet
                        relation = "admin"
                        
                    writes.append(ClientTuple(
                        user=f"user:{member.user_id}",
                        relation=relation,
                        object=f"workspace:{ws.id}"
                    ))

            # Execute Writes
            batch_size = 10
            for i in range(0, len(writes), batch_size):
                batch = writes[i:i+batch_size]
                try:
                    await real_fga_client.write(ClientWriteRequest(writes=batch))
                    logger.info(f"Wrote batch of {len(batch)} tuples.")
                except Exception as e:
                    logger.error(f"Failed to write batch {i}: {e}")

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
