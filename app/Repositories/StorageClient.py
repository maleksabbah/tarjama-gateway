"""
HTTP client for the downstream Storage service.
Routes call this via FileProxyService — they never touch httpx directly.
"""
from typing import Any, Optional

import httpx

from app.Config.Config import config


class StorageClient:
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
        url = f"{config.STORAGE_URL}{path}"
        headers = {"X-User-ID": str(user_id)}
        resp = await self.client.request(
            method, url, json=json, params=params, headers=headers,
        )
        try:
            body = resp.json()
        except ValueError:
            body = {"detail": resp.text or "Storage error"}
        return resp.status_code, body

    async def get_presign(self, user_id: int) -> tuple[int, Any]:
        return await self._request(
            "POST", "/files/presign", user_id=user_id,
            params={"user_id": user_id},
        )

    async def list_files(self, user_id: int, job_id: str) -> tuple[int, Any]:
        return await self._request(
            "GET", "/files", user_id=user_id,
            params={"job_id": job_id, "user_id": user_id},
        )

    async def download_url(self, user_id: int, file_id: str) -> tuple[int, Any]:
        return await self._request(
            "GET", f"/files/{file_id}/download", user_id=user_id,
            params={"user_id": user_id},
        )