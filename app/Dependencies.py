"""
FastAPI dependency factories.
One place where per-request services are assembled with their repos.
"""
from typing import AsyncIterator

import httpx
from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.Config.Database import SessionLocal
from app.Entities import User
from app.Repositories import (
    UserRepository,
    OrchestratorClient,
    StorageClient,
)
from app.Services import (
    AuthService,
    UserService,
    JobProxyService,
    FileProxyService,
)


# ─── Per-request session ────────────────────────────────────────────────

async def get_db_session() -> AsyncIterator[AsyncSession]:
    session = SessionLocal()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


# ─── Shared HTTP client (built once in main.py lifespan) ────────────────

def get_http_client(request: Request) -> httpx.AsyncClient:
    return request.app.state.http_client


# ─── Repositories ───────────────────────────────────────────────────────

def get_user_repo(
    session: AsyncSession = Depends(get_db_session),
) -> UserRepository:
    return UserRepository(session)


def get_orchestrator_client(
    http: httpx.AsyncClient = Depends(get_http_client),
) -> OrchestratorClient:
    return OrchestratorClient(http)


def get_storage_client(
    http: httpx.AsyncClient = Depends(get_http_client),
) -> StorageClient:
    return StorageClient(http)


# ─── Services ───────────────────────────────────────────────────────────

def get_auth_service(
    users: UserRepository = Depends(get_user_repo),
) -> AuthService:
    return AuthService(users=users)


def get_user_service(
    users: UserRepository = Depends(get_user_repo),
) -> UserService:
    return UserService(users=users)


def get_job_proxy_service(
    client: OrchestratorClient = Depends(get_orchestrator_client),
    users: UserService = Depends(get_user_service),
) -> JobProxyService:
    return JobProxyService(client=client, users=users)


def get_file_proxy_service(
    client: StorageClient = Depends(get_storage_client),
    users: UserService = Depends(get_user_service),
) -> FileProxyService:
    return FileProxyService(client=client, users=users)


# ─── Current user resolution ────────────────────────────────────────────

async def current_user(
    request: Request,
    auth: AuthService = Depends(get_auth_service),
) -> User:
    return await auth.resolve_current_user(request)