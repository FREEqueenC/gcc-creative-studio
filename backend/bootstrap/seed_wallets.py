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
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import SessionLocal, engine, Base
from src.users.user_model import User
from src.credits.credit_model import UserWallet
from src.organizations.organization_model import Organization
from src.credits.credit_model import OrganizationWallet

async def seed_user_wallets(db: AsyncSession):
    print("Seeding user wallets...")
    result = await db.execute(select(User))
    users = result.scalars().all()
    
    wallets_created = 0
    for user in users:
        existing_wallet = await db.execute(
            select(UserWallet).filter(UserWallet.user_id == user.id)
        )
        if not existing_wallet.scalar_one_or_none():
            wallet = UserWallet(user_id=user.id, balance=0.0)
            db.add(wallet)
            wallets_created += 1
            print(f"Created wallet for user {user.id} ({user.email})")
        
    if wallets_created > 0:
        await db.commit()
        print(f"Committed {wallets_created} new user wallets.")
    else:
        print("No new user wallets needed.")

async def seed_organization_wallets(db: AsyncSession):
    print("Seeding organization wallets...")
    result = await db.execute(select(Organization))
    organizations = result.scalars().all()
    
    wallets_created = 0
    for org in organizations:
        existing_wallet = await db.execute(
            select(OrganizationWallet).filter(OrganizationWallet.organization_id == org.id)
        )
        if not existing_wallet.scalar_one_or_none():
            wallet = OrganizationWallet(organization_id=org.id, balance=0.0)
            db.add(wallet)
            wallets_created += 1
            print(f"Created wallet for organization {org.id} ({org.name})")
            
    if wallets_created > 0:
        await db.commit()
        print(f"Committed {wallets_created} new organization wallets.")
    else:
        print("No new organization wallets needed.")

async def main():
    async with SessionLocal() as db:
        await seed_user_wallets(db)
        await seed_organization_wallets(db)

if __name__ == "__main__":
    print("Starting wallet seeding script...")
    asyncio.run(main())
    print("Wallet seeding script finished.")
