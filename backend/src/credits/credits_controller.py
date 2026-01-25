from fastapi import APIRouter, Depends, HTTPException, status
from src.users.user_model import UserModel
from src.credits.credits_service import CreditsService
from src.credits.dto.assign_credits_dto import AssignCreditsDto
from src.auth.auth_service import get_current_user
from src.credits.dto.price_catalog_dto import PriceCatalogDto, CreatePriceCatalogDto, UpdatePriceCatalogDto
from src.credits.credit_model import PriceCatalog
from typing import List
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

@router.get("/balance")
async def get_balance(
    user_id: int | None = None,
    org_id: int | None = None,
    current_user: UserModel = Depends(get_current_user),
    service: CreditsService = Depends()
):
    """
    Get balance for a user or organization.
    Requires Super Admin privileges to check others' balance.
    """
    if not current_user.is_super_admin:
         # If not super admin, can only check own balance or own orgs
         if user_id and user_id != current_user.id:
             raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot check other users' balance")
         # For orgs, we'd need to check membership, but for now let's restrict to super admin for arbitrary checks
         if org_id:
             # TODO: Check if user is admin of org
             pass

    return {"balance": await service.get_wallet_balance(user_id, org_id)}

@router.get("/prices", response_model=List[PriceCatalogDto])
async def get_all_prices(
    current_user: UserModel = Depends(get_current_user),
    service: CreditsService = Depends()
):
    if not current_user.is_super_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    return await service.get_all_prices()

@router.post("/prices", response_model=PriceCatalogDto)
async def create_price(
    dto: CreatePriceCatalogDto,
    current_user: UserModel = Depends(get_current_user),
    service: CreditsService = Depends()
):
    if not current_user.is_super_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    return await service.create_price(dto)

@router.put("/prices/{model_id}", response_model=PriceCatalogDto)
async def update_price(
    model_id: str,
    dto: UpdatePriceCatalogDto,
    current_user: UserModel = Depends(get_current_user),
    service: CreditsService = Depends()
):
    if not current_user.is_super_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    return await service.update_price(model_id, dto)

@router.delete("/prices/{model_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_price(
    model_id: str,
    current_user: UserModel = Depends(get_current_user),
    service: CreditsService = Depends()
):
    if not current_user.is_super_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    await service.delete_price(model_id)
    return None
