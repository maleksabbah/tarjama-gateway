"""
File proxy service.
Forwards file operations to the Storage service.
Translates downstream errors into HTTP exceptions.
"""
from typing import Any

from fastapi import HTTPException

from app.Repositories import StorageClient
from app.Services.UserService import UserService
from app.ExceptionHandler import QuotaExceeded


class FileProxyService:
    def __init__(self, client: StorageClient, users: UserService):
        self.client = client
        self.users = users
    async def get_presign(self, user_id: int) -> Any:
        await self._ensure_quota(user_id)
        status, body = await self.client.get_presign(user_id)
        return _unwrap(status,body,"Storage")
    async def list_files(self, user_id: int,job_id: str) -> Any:
        status, body = await self.client.list_files(user_id, job_id)
        return _unwrap(status,body,"Storage")
    async def download_url(self,user_id:int,file_id:str)-> Any:
        status, body = await self.client.download_url(user_id, file_id)
        return _unwrap(status,body,"Storage")
    async def _ensure_quota(self,user_id: int) -> None:
        quota = await self.users.get_quota(user_id)
        if not quota["has_quota"]:
            raise QuotaExceeded(
                "Monthly usage exhausted",
                quota = quota["quota"],
                used=quota["used"],
            )
def _unwrap(status:int,body:Any,source:str)-> Any :
    if 200 <= status < 300:
        return body
    detail = body if body else {"detail": f"{source} error"}
    raise HTTPException(status_code=status, detail=detail)




