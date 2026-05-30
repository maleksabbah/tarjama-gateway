"""
User lifecycle service.
Register, fetch, quota lookup, usage tracking.
"""
from app.Entities import User
from app.Repositories import UserRepository
from app.Services.AuthService import AuthService
from app.ExceptionHandler import EmailAlreadyExists, UserNotFound


class UserService:
    def __init__(self, users: UserRepository):
        self.users = users

    async def register(self, email: str, password: str) -> User:
        existing = await self.users.get_by_email(email)
        if existing:
            raise EmailAlreadyExists(email)

        password_hash = AuthService.hash_password(password)
        api_key = AuthService.generate_api_key()
        return await self.users.create(
            email=email,
            password_hash=password_hash,
            api_key=api_key,
        )

    async def get(self, user_id: int) -> User:
        user = await self.users.get(user_id)
        if not user:
            raise UserNotFound(user_id)
        return user

    async def get_quota(self, user_id: int) -> dict:
        user = await self.get(user_id)
        remaining = user.quota_minutes - user.used_minutes
        return {
            "has_quota": remaining > 0,
            "remaining": max(0.0, remaining),
            "quota": user.quota_minutes,
            "used": user.used_minutes,
        }

    async def add_used_minutes(self, user_id: int, minutes: float) -> None:
        await self.users.increment_used_minutes(user_id, minutes)

