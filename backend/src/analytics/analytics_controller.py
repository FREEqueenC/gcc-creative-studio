from fastapi import APIRouter, Depends
from src.auth.auth_service import get_current_user
from src.users.user_model import UserModel
from src.analytics.analytics_service import AnalyticsService

router = APIRouter(prefix="/api/analytics", tags=["Analytics"])

@router.get("/token-usage")
async def get_token_usage(
    current_user: UserModel = Depends(get_current_user),
    service: AnalyticsService = Depends()
):
    return await service.get_token_usage()

@router.get("/token-budgets")
async def get_token_budgets(
    current_user: UserModel = Depends(get_current_user),
    service: AnalyticsService = Depends()
):
    return await service.get_token_budgets()

@router.get("/active-roles")
async def get_active_roles(
    current_user: UserModel = Depends(get_current_user),
    service: AnalyticsService = Depends()
):
    return await service.get_active_roles()

# User Profile Endpoint (technically under /api/users but placed here for convenience or we can add another router)
# The requirement said: GET /api/users/me/profile
# I'll put it in a separate router or same one with different prefix?
# I'll add it to this router but with /api/users/me/profile path?
# No, router prefix is /api/analytics.
# I should create a separate router for /api/users/me/profile or add it to user_controller.
# But the user grouped it under "Analytics & Dashboard Endpoints".
# I'll add it here as /api/users/me/profile if I can override prefix, or just /users/me/profile if I change prefix.
# I'll create a separate router for this endpoint to match the path exactly.

@router.get("/organizations/{org_id}/usage")
async def get_organization_usage(
    org_id: int,
    current_user: UserModel = Depends(get_current_user),
    service: AnalyticsService = Depends()
):
    # TODO: Add permission check (Org Admin or Super Admin)
    return await service.get_organization_usage(org_id)

@router.get("/users/{user_id}/usage")
async def get_user_usage(
    user_id: int,
    current_user: UserModel = Depends(get_current_user),
    service: AnalyticsService = Depends()
):
    # TODO: Add permission check (Self or Admin)
    return await service.get_user_usage(user_id)
