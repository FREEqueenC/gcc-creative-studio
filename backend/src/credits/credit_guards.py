from typing import Optional, AsyncGenerator, Type, Callable
from fastapi import Depends, Request, Body
from src.auth.auth_service import get_current_user
from src.users.user_model import UserModel
from src.credits.credits_service import CreditsService
from src.common.base_dto import BaseDto

def check_and_log_credits(dto_type: Type[BaseDto]):
    """
    Dependency factory that checks for sufficient credits before execution
    and deducts them after successful execution, based on the request DTO.
    """
    async def dependency(
        request: Request,
        dto: dto_type = Body(...),
        current_user: UserModel = Depends(get_current_user),
        service: CreditsService = Depends()
    ) -> AsyncGenerator[None, None]:
        # 1. Calculate Cost from DTO
        cost = await service.calculate_cost(dto)
        
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
        if cost > 0:
            org_id_header = request.headers.get("X-Organization-ID")
            org_id = int(org_id_header) if org_id_header and org_id_header.isdigit() else None
            model_id = getattr(dto, 'generation_model', getattr(dto, 'model', 'unknown'))
            await service.deduct_credits(current_user.id, cost, str(model_id), org_id)

    return dependency
