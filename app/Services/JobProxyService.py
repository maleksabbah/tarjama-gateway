# app/Services/JobProxyService.py
"""
Job proxy service.
Forwards job operations to the orchestrator.
Translates downstream errors into HTTP exceptions.
"""
from typing import Any

from fastapi import HTTPException

from app.Repositories import OrchestratorClient
from app.Services.UserService import UserService
from app.ExceptionHandler import QuotaExceeded


class JobProxyService:
    def __init__(
        self,
        client: OrchestratorClient,
        users: UserService,
    ):
        self.client = client
        self.users = users

    async def create_job(self, user_id: int, body: dict) -> Any:
        await self._ensure_quota(user_id)
        # Inject the trusted user_id; ignore anything the client sent.
        payload = {**body, "user_id": user_id}
        status, body_out = await self.client.create_job(user_id, payload)
        return _unwrap(status, body_out, "Orchestrator")

    async def list_jobs(self, user_id: int, limit: int, offset: int) -> Any:
        status, body = await self.client.list_jobs(user_id, limit, offset)
        return _unwrap(status, body, "Orchestrator")

    async def get_job(self, user_id: int, job_id: str) -> Any:
        status, body = await self.client.get_job(user_id, job_id)
        return _unwrap(status, body, "Orchestrator")

    async def get_progress(self, user_id: int, job_id: str) -> Any:
        status, body = await self.client.get_progress(user_id, job_id)
        return _unwrap(status, body, "Orchestrator")

    async def cancel_job(self, user_id: int, job_id: str) -> Any:
        status, body = await self.client.cancel_job(user_id, job_id)
        return _unwrap(status, body, "Orchestrator")

    async def _ensure_quota(self, user_id: int) -> None:
        quota = await self.users.get_quota(user_id)
        if not quota["has_quota"]:
            raise QuotaExceeded(
                "Monthly quota exhausted",
                quota=quota["quota"],
                used=quota["used"],
            )


def _unwrap(status: int, body: Any, source: str) -> Any:
    if 200 <= status < 300:
        return body
    detail = body if body else {"detail": f"{source} error"}
    raise HTTPException(status_code=status, detail=detail)