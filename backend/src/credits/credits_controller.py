from fastapi import APIRouter, Depends, HTTPException, status
from src.users.user_model import UserModel
from src.credits.credits_service import CreditsService
from src.credits.dto.assign_credits_dto import AssignCreditsDto
from src.auth.auth_service import get_current_user

router = APIRouter(prefix="/api/credits", tags=["Credits"])

@router.post("/assign")
async def assign_credits(
    dto: AssignCreditsDto,
    current_user: UserModel = Depends(get_current_user),
    service: CreditsService = Depends()
):
    """
    Assigns credits to a user or organization.
    Requires Super Admin privileges.
    """
    if not current_user.is_super_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Super Admins can assign credits."
        )
    
    return await service.assign_credits(dto, current_user)
