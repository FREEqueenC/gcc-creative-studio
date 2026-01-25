from typing import Optional, AsyncGenerator
from fastapi import Depends, Request
from src.auth.auth_service import get_current_user
from src.users.user_model import UserModel
from src.credits.credits_service import CreditsService

def check_and_log_credits(model_id: str):
    """
    Dependency factory that checks for sufficient credits before execution
    and deducts them after successful execution.
    """
    async def dependency(
        request: Request,
        current_user: UserModel = Depends(get_current_user),
        service: CreditsService = Depends()
    ) -> AsyncGenerator[None, None]:
        # 1. Fetch Cost
        price = await service.get_price(model_id)
        cost = price.cost if price else 0.0
        
        if cost > 0:
            # 2. Check Balance (Gatekeeper)
            org_id_header = request.headers.get("X-Organization-ID")
            org_id = int(org_id_header) if org_id_header and org_id_header.isdigit() else None
            
            has_balance = await service.check_balance(current_user.id, cost, org_id)
            
            if not has_balance:
                from src.config.config_service import config_service
                if config_service.CREDIT_SYSTEM_MODE == "ENFORCED":
                    from fastapi import HTTPException
                    raise HTTPException(status_code=402, detail="Insufficient credits")

        yield # Proceed with request

        # 3. Deduct Credits (Post-Generation)
        # This runs only if the route handler completed successfully (no exception raised)
        if cost > 0:
            # Try to get org_id from headers if available (e.g. X-Organization-ID)
            org_id_header = request.headers.get("X-Organization-ID")
            org_id = int(org_id_header) if org_id_header and org_id_header.isdigit() else None
            
            await service.deduct_credits(current_user.id, cost, model_id, org_id)

    return dependency
