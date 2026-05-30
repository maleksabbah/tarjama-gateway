from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.Entities import User


class UserRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, email: str, password_hash: str, api_key: str) -> User:
        user = User(email=email, password_hash=password_hash, api_key=api_key)
        self.session.add(user)
        await self.session.flush()
        return user

    async def get(self, user_id: int) -> Optional[User]:
        result = await self.session.execute(
            select(User).where(User.id == user_id, User.is_active.is_(True))
        )
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> Optional[User]:
        result = await self.session.execute(
            select(User).where(User.email == email, User.is_active.is_(True))
        )
        return result.scalar_one_or_none()

    async def get_by_api_key(self, api_key: str) -> Optional[User]:
        result = await self.session.execute(
            select(User).where(User.api_key == api_key, User.is_active.is_(True))
        )
        return result.scalar_one_or_none()

    async def increment_used_minutes(self, user_id: int, minutes: float) -> None:
        await self.session.execute(
            update(User)
            .where(User.id == user_id)
            .values(used_minutes=User.used_minutes + minutes)
        )