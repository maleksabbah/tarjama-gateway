"""
HTTP client for the downstream orchestrator service.
Routes call this via JobProxyService — they never touch httpx directly.
"""
from typing import Any, Optional

import httpx

from app.Config.Config import config


class OrchestratorClient:
    def __init__(self, client: httpx.AsyncClient):
        self.client = client

    async def _request(
        self,
        method: str,
        path: str,
        *,
        user_id: int,
        json: Optional[dict] = None,
        params: Optional[dict] = None,
    ) -> tuple[int, Any]:
        url = f"{config.ORCHESTRATOR_URL}{path}"
        headers = {"X-User-ID": str(user_id)}
        resp = await self.client.request(
            method, url, json=json, params=params, headers=headers,
        )
        try:
            body = resp.json()
        except ValueError:
            body = {"detail": resp.text or "Orchestrator error"}
        return resp.status_code, body

    async def create_job(self, user_id: int, payload: dict) -> tuple[int, Any]:
        return await self._request("POST", "/jobs", user_id=user_id, json=payload)

    async def list_jobs(
        self, user_id: int, limit: int, offset: int,
    ) -> tuple[int, Any]:
        return await self._request(
            "GET", "/jobs", user_id=user_id,
            params={"user_id": user_id, "limit": limit, "offset": offset},
        )

    async def get_job(self, user_id: int, job_id: str) -> tuple[int, Any]:
        return await self._request(
            "GET", f"/jobs/{job_id}", user_id=user_id,
            params={"user_id": user_id},
        )

    async def get_progress(self, user_id: int, job_id: str) -> tuple[int, Any]:
        return await self._request(
            "GET", f"/jobs/{job_id}/progress", user_id=user_id,
            params={"user_id": user_id},
        )

    async def cancel_job(self, user_id: int, job_id: str) -> tuple[int, Any]:
        return await self._request(
            "POST", f"/jobs/{job_id}/cancel", user_id=user_id,
            params={"user_id": user_id},
        )