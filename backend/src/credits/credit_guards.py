from typing import Optional, AsyncGenerator, Type, Callable
from fastapi import Depends, Request, Body, HTTPException
from src.auth.auth_service import get_current_user
from src.users.user_model import UserModel
from src.credits.credits_service import CreditsService
from src.common.base_dto import BaseDto
from src.config.config_service import config_service

def check_and_log_credits(dto_type: Type[BaseDto]):
    """
    Dependency factory that checks for sufficient credits before execution
    and deducts them after successful execution, based on the request DTO.
    """
    async def dependency(
        request: Request,
        current_user: UserModel = Depends(get_current_user),
        service: CreditsService = Depends()
    ) -> AsyncGenerator[None, None]:
        # 1. Manually Extract and Validate DTO from Request
        try:
            # request.json() is cached, so the main route handler can call it again later safely
            body_payload = await request.json()
            # Manually instantiate the DTO
            dto = dto_type(**body_payload)
        except Exception:
            # If JSON is invalid, we allow the main route handler to raise the specific validation error later,
            # or we can raise a generic one here.
            # For safety, if we can't parse cost, we shouldn't run.
            raise HTTPException(status_code=422, detail="Unable to process request for credit calculation")
        
        # 2. Calculate Cost from DTO
        cost = await service.calculate_cost(dto)
        
        if cost > 0:
            # 3. Check Balance (Gatekeeper)
            org_id_header = request.headers.get("X-Organization-ID")
            org_id = int(org_id_header) if org_id_header and org_id_header.isdigit() else None
            
            has_balance = await service.check_balance(current_user.id, cost, org_id)
            
            if not has_balance:
                if config_service.CREDIT_SYSTEM_MODE == "ENFORCED":
                    raise HTTPException(status_code=402, detail="Insufficient credits")

        # 4. Deduct Credits (Pre-Generation)
        if cost > 0:
            org_id_header = request.headers.get("X-Organization-ID")
            org_id = int(org_id_header) if org_id_header and org_id_header.isdigit() else None
            model_id = getattr(dto, 'generation_model', getattr(dto, 'model', 'unknown'))
            await service.deduct_credits(current_user.id, cost, model_id.value, org_id)

        yield # Proceed with request

    return dependency
