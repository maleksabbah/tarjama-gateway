"""
Auth service.
Pure DI: receives a UserRepository for any DB lookup. Owns no session.
Exposes password hashing, API key generation, JWT encode/decode, and
current-user resolution from a request's Authorization / X-API-Key headers.
"""
import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Request

from app.Config.Config import config
from app.Entities import User
from app.Repositories import UserRepository
from app.ExceptionHandler import (
    InvalidCredentials,
    InvalidToken,
    TokenExpired,
    MissingAuth,
    UserNotFound,
)


class AuthService:
    def __init__(self, users: UserRepository):
        self.users = users

    @staticmethod
    def hash_password(password: str) -> str:
        return bcrypt.hashpw(
            password.encode("utf-8"), bcrypt.gensalt()
        ).decode("utf-8")

    @staticmethod
    def verify_password(password: str, hashed: str) -> bool:
        return bcrypt.checkpw(
            password.encode("utf-8"), hashed.encode("utf-8")
        )

    @staticmethod
    def generate_api_key() -> str:
        return f"ask_{secrets.token_hex(32)}"

    @staticmethod
    def create_access_token(user_id: int) -> str:
        payload = {
            "sub": str(user_id),
            "type": "access",
            "exp": datetime.now(timezone.utc)
                + timedelta(minutes=config.JWT_ACCESS_TOKEN_EXPIRE_MINUTES),
            "iat": datetime.now(timezone.utc),
        }
        return jwt.encode(payload, config.JWT_SECRET, algorithm=config.JWT_ALGORITHM)

    @staticmethod
    def create_refresh_token(user_id: int) -> str:
        payload = {
            "sub": str(user_id),
            "type": "refresh",
            "exp": datetime.now(timezone.utc)
                + timedelta(days=config.JWT_REFRESH_TOKEN_EXPIRE_DAYS),
            "iat": datetime.now(timezone.utc),
        }
        return jwt.encode(payload, config.JWT_SECRET, algorithm=config.JWT_ALGORITHM)

    @staticmethod
    def decode_token(token: str) -> dict:
        try:
            payload = jwt.decode(
                token, config.JWT_SECRET, algorithms=[config.JWT_ALGORITHM]
            )
            payload["sub"] = int(payload["sub"])
            return payload
        except jwt.ExpiredSignatureError:
            raise TokenExpired()
        except jwt.InvalidTokenError:
            raise InvalidToken()

    async def login(self, email: str, password: str) -> tuple[str, str]:
        user = await self.users.get_by_email(email)
        if not user or not self.verify_password(password, user.password_hash):
            raise InvalidCredentials()
        return (
            self.create_access_token(user.id),
            self.create_refresh_token(user.id),
        )

    async def refresh(self, refresh_token: str) -> tuple[str, str]:
        payload = self.decode_token(refresh_token)
        if payload.get("type") != "refresh":
            raise InvalidToken("Invalid token type")

        user = await self.users.get(payload["sub"])
        if not user:
            raise UserNotFound(payload["sub"])

        return (
            self.create_access_token(user.id),
            self.create_refresh_token(user.id),
        )

    async def resolve_current_user(self, request: Request) -> User:
        api_key = request.headers.get("X-API-Key")
        if api_key:
            user = await self.users.get_by_api_key(api_key)
            if not user:
                raise InvalidToken("Invalid API key")
            return user

        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise MissingAuth()

        token = auth_header.split(" ", 1)[1]
        payload = self.decode_token(token)

        if payload.get("type") != "access":
            raise InvalidToken("Invalid token type")

        user = await self.users.get(payload["sub"])
        if not user:
            raise UserNotFound(payload["sub"])
        return user

    async def resolve_user_from_token(self, token: str) -> User:
        """Used by WebSockets — JWT comes via ?token=... query param."""
        if not token:
            raise MissingAuth()
        payload = self.decode_token(token)
        if payload.get("type") != "access":
            raise InvalidToken("Invalid token type")
        user = await self.users.get(payload["sub"])
        if not user:
            raise UserNotFound(payload["sub"])
        return user




