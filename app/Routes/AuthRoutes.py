"""
Auth routes — register, login, refresh.
"""
from fastapi import APIRouter, Depends

from app.Services import AuthService, UserService
from app.Dependencies import get_auth_service, get_user_service
from app.Dtos import (
    RegisterRequest,
    LoginRequest,
    RefreshRequest,
    TokenResponse,
    UserResponse,
)


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserResponse, status_code=201)
async def register(
    req: RegisterRequest,
    users: UserService = Depends(get_user_service),
) -> UserResponse:
    user = await users.register(email=req.email, password=req.password)
    return UserResponse.model_validate(user)


@router.post("/login", response_model=TokenResponse)
async def login(
    req: LoginRequest,
    auth: AuthService = Depends(get_auth_service),
) -> TokenResponse:
    access, refresh_token = await auth.login(req.email, req.password)
    return TokenResponse(access_token=access, refresh_token=refresh_token)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    req: RefreshRequest,
    auth: AuthService = Depends(get_auth_service),
) -> TokenResponse:
    access, new_refresh = await auth.refresh(req.refresh_token)
    return TokenResponse(access_token=access, refresh_token=new_refresh)