"""
User self-service routes (kept under /auth/* to preserve the public surface).
"""
from fastapi import APIRouter, Depends, Response

from app.Entities import User
from app.Services import UserService
from app.Dependencies import current_user, get_user_service
from app.Dtos import UserResponse, QuotaResponse


router = APIRouter(prefix="/auth", tags=["user"])


@router.get("/me", response_model=UserResponse)
async def me(
    response: Response,
    user: User = Depends(current_user),
) -> UserResponse:
    # X-User-ID header lets nginx forward the verified user id to the
    # orchestrator after auth_request (used for WebSocket auth).
    response.headers["X-User-ID"] = str(user.id)
    return UserResponse.model_validate(user)


@router.get("/quota", response_model=QuotaResponse)
async def quota(
    user: User = Depends(current_user),
    users: UserService = Depends(get_user_service),
) -> QuotaResponse:
    return QuotaResponse(**await users.get_quota(user.id))



