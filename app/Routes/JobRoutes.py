"""
Job routes — auth, then delegate to JobProxyService.
"""
from fastapi import APIRouter, Depends, Query

from app.Entities import User
from app.Services import JobProxyService
from app.Dependencies import current_user, get_job_proxy_service
from app.Dtos import CreateJobRequest

router = APIRouter(prefix="/jobs", tags=["jobs"])

@router.post("")
async def create_job(
        req: CreateJobRequest,
        user: User = Depends(current_user),
        jobs: JobProxyService = Depends(get_job_proxy_service)
):
    return await jobs.create_job(user.id, req.model_dump())

@router.get("")
async def list_jobs(
        user: User = Depends(current_user),
        jobs: JobProxyService = Depends(get_job_proxy_service),
        limit: int = Query(50, ge=1, le=50),
        offset: int = Query(0, ge=0)

):
    return await jobs.list_jobs(user.id, limit, offset)
@router.get("/{job_id}/progress")
async def get_progress(
        job_id: str,
        user: User = Depends(current_user),
        jobs: JobProxyService = Depends(get_job_proxy_service)
):
    return await jobs.get_progress(user.id, job_id)

@router.get("/{job_id}/cancel")
async def cancel_job(
        job_id: str,
        user: User = Depends(current_user),
        jobs: JobProxyService = Depends(get_job_proxy_service)
):
    return await jobs.cancel_job(user.id, job_id)
