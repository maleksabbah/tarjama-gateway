"""
File routes — proxy to the Storage service.

Gateway authenticates + quota-checks (inside FileProxyService),
then forwards. The resolved user_id is always taken from the JWT —
never trusted from the client.

  POST /api/upload/presign        -> presigned PUT URL for upload
  GET  /api/files/{job_id}        -> list output files for a job
  GET  /api/files/download/{id}   -> presigned GET URL for one file
"""
from fastapi import APIRouter, Depends

from app.Entities import User
from app.Services import FileProxyService
from app.Dependencies import current_user, get_file_proxy_service

router = APIRouter(tags=["files"])


@router.post("/upload/presign")
async def presign_upload(
    user: User = Depends(current_user),
    files: FileProxyService = Depends(get_file_proxy_service),
):
    return await files.get_presign(user.id)


@router.get("/files/{job_id}")
async def list_files(
    job_id: str,
    user: User = Depends(current_user),
    files: FileProxyService = Depends(get_file_proxy_service),
):
    return await files.list_files(user.id, job_id)


@router.get("/files/download/{file_id}")
async def download_file(
    file_id: str,
    user: User = Depends(current_user),
    files: FileProxyService = Depends(get_file_proxy_service),
):
    return await files.download_url(user.id, file_id)