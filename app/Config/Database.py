from contextlib import asynccontextmanager
from typing import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.Config.Config import config


db_url = config.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")

engine = create_async_engine(
    db_url,
    pool_size=config.DB_POOL_MAX,
    pool_pre_ping=True,
    echo=False,
)

SessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


@asynccontextmanager
async def get_session() -> AsyncIterator[AsyncSession]:
    session = SessionLocal()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


async def close_db() -> None:
    await engine.dispose()