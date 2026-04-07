"""
Gateway Routes
Auth endpoints + proxies to Orchestrator and Storage Service.
Option B: Presigned URL upload — Gateway never touches file bytes.
"""
import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.Config import config
from app.Auth import (
    hash_password,
    verify_password,
    generate_api_key,
    create_access_token,
    create_refresh_token,
    decode_token,
    get_current_user,
)

from app.Database import (
    create_user,
    get_user_by_email,
    check_quota,
)
from app.Rate_limiter import check_rate_limit, check_upload_rate
from app.Schemas import (
    RegisterRequest,
    LoginRequest,
    TokenResponse,
    RefreshRequest,
    UserResponse,
    CreateJobRequest,
)

router = APIRouter()
security = HTTPBearer()


# =============================================================================
# Auth endpoints (unchanged)
# =============================================================================

@router.post("/auth/register", response_model=UserResponse)
async def register(req: RegisterRequest):
    existing = await get_user_by_email(req.email)
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    if len(req.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    user = await create_user(
        email=req.email,
        password_hash=hash_password(req.password),
        api_key=generate_api_key(),
    )
    return user


@router.post("/auth/login", response_model=TokenResponse)
async def login(req: LoginRequest):
    user = await get_user_by_email(req.email)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if not verify_password(req.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    return TokenResponse(
        access_token=create_access_token(user["id"]),
        refresh_token=create_refresh_token(user["id"]),
    )


@router.post("/auth/refresh", response_model=TokenResponse)
async def refresh(req: RefreshRequest):
    payload = decode_token(req.refresh_token)
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    return TokenResponse(
        access_token=create_access_token(payload["sub"]),
        refresh_token=create_refresh_token(payload["sub"]),
    )


@router.get("/auth/me", response_model=UserResponse)
async def me(credentials: HTTPAuthorizationCredentials = Depends(security),
             user: dict = Depends(get_current_user)):
    return user


@router.get("/auth/quota")
async def quota(credentials: HTTPAuthorizationCredentials = Depends(security),
                user: dict = Depends(get_current_user)):
    return await check_quota(user["id"])


# =============================================================================
# Upload endpoint — presigned URL flow (Gateway never touches the file)
# =============================================================================

@router.post("/upload/presign")
async def get_upload_url(credentials: HTTPAuthorizationCredentials = Depends(security),
                         user: dict = Depends(get_current_user)):
    """
    Step 1: Get a presigned URL for direct upload to S3.

    Flow:
      1. User calls this endpoint
      2. Gateway checks auth, rate limit, quota
      3. Gateway asks Storage Service to generate a presigned URL
      4. User receives the URL and uploads directly to MinIO
      5. User then calls POST /api/jobs with the returned s3_key

    Returns:
      upload_url: presigned PUT URL for direct upload to MinIO
      s3_key: the S3 path to use when creating the job
    """
    await check_upload_rate(user["id"])

    quota_info = await check_quota(user["id"])
    if not quota_info["has_quota"]:
        raise HTTPException(status_code=403, detail="Quota exceeded")

    return await _proxy_to_storage(
        "POST",
        f"/files/presign?user_id={user['id']}",
        user,
    )


# =============================================================================
# Job endpoints (proxy to Orchestrator)
# =============================================================================

async def _proxy_to_orchestrator(method: str, path: str, user: dict, json: dict = None):
    """Forward request to Orchestrator with user context."""
    url = f"{config.ORCHESTRATOR_URL}{path}"
    headers = {"X-User-ID": str(user["id"])}

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            if method == "GET":
                resp = await client.get(url, headers=headers)
            elif method == "POST":
                resp = await client.post(url, headers=headers, json=json)
            else:
                raise HTTPException(status_code=405, detail="Method not allowed")

            if resp.status_code >= 400:
                raise HTTPException(status_code=resp.status_code, detail=resp.json().get("detail", "Orchestrator error"))
            return resp.json()
        except httpx.ConnectError:
            raise HTTPException(status_code=503, detail="Orchestrator service unavailable")


@router.post("/jobs")
async def create_job(req: CreateJobRequest,
                     credentials: HTTPAuthorizationCredentials = Depends(security),
                     user: dict = Depends(get_current_user)):
    await check_rate_limit(user["id"], "create_job")

    quota_info = await check_quota(user["id"])
    if not quota_info["has_quota"]:
        raise HTTPException(status_code=403, detail="Quota exceeded")

    return await _proxy_to_orchestrator("POST", "/jobs", user, json={
        "user_id": user["id"],
        "file_path": req.file_path,
        "dialect": req.dialect,
        "output_type": req.output_type,
        "subtitle_format": req.subtitle_format,
        "burn_subtitles": req.burn_subtitles,
    })


@router.get("/jobs")
async def list_jobs(credentials: HTTPAuthorizationCredentials = Depends(security),
                    user: dict = Depends(get_current_user)):
    await check_rate_limit(user["id"], "list_jobs")
    return await _proxy_to_orchestrator("GET", f"/jobs?user_id={user['id']}", user)


@router.get("/jobs/{job_id}")
async def get_job(job_id: str,
                  credentials: HTTPAuthorizationCredentials = Depends(security),
                  user: dict = Depends(get_current_user)):
    await check_rate_limit(user["id"], "get_job")
    return await _proxy_to_orchestrator("GET", f"/jobs/{job_id}", user)


@router.get("/jobs/{job_id}/progress")
async def get_progress(job_id: str,
                       credentials: HTTPAuthorizationCredentials = Depends(security),
                       user: dict = Depends(get_current_user)):
    await check_rate_limit(user["id"], "get_progress")
    return await _proxy_to_orchestrator("GET", f"/jobs/{job_id}/progress", user)


@router.post("/jobs/{job_id}/cancel")
async def cancel_job(job_id: str,
                     credentials: HTTPAuthorizationCredentials = Depends(security),
                     user: dict = Depends(get_current_user)):
    return await _proxy_to_orchestrator("POST", f"/jobs/{job_id}/cancel", user)


# =============================================================================
# File endpoints (proxy to Storage Service)
# =============================================================================

async def _proxy_to_storage(method: str, path: str, user: dict):
    """Forward request to Storage Service."""
    url = f"{config.STORAGE_URL}{path}"
    headers = {"X-User-ID": str(user["id"])}

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            if method == "GET":
                resp = await client.get(url, headers=headers)
            elif method == "POST":
                resp = await client.post(url, headers=headers)
            else:
                raise HTTPException(status_code=405, detail="Method not allowed")

            if resp.status_code >= 400:
                raise HTTPException(status_code=resp.status_code, detail=resp.json().get("detail", "Orchestrator error"))
            return resp.json()
        except httpx.ConnectError:
            raise HTTPException(status_code=503, detail="Storage service unavailable")


@router.get("/files/{job_id}")
async def list_files(job_id: str,
                     credentials: HTTPAuthorizationCredentials = Depends(security),
                     user: dict = Depends(get_current_user)):
    await check_rate_limit(user["id"], "list_files")
    return await _proxy_to_storage("GET", f"/files?job_id={job_id}&user_id={user['id']}", user)


@router.get("/files/download/{file_id}")
async def download_file(file_id: str,
                        credentials: HTTPAuthorizationCredentials = Depends(security),
                        user: dict = Depends(get_current_user)):
    await check_rate_limit(user["id"], "download")
    return await _proxy_to_storage("GET", f"/files/{file_id}/download?user_id={user['id']}", user)