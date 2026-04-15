"""
Gateway Routes
Auth endpoints + proxies to Orchestrator and Storage Service.
Option B: Presigned URL upload — Gateway never touches file bytes.
"""
import asyncio
import json
import httpx
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, Query
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
# Auth endpoints
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
# Upload endpoint — presigned URL flow
# =============================================================================

@router.post("/upload/presign")
async def get_upload_url(credentials: HTTPAuthorizationCredentials = Depends(security),
                         user: dict = Depends(get_current_user)):
    await check_upload_rate(user["id"])
    quota_info = await check_quota(user["id"])
    if not quota_info["has_quota"]:
        raise HTTPException(status_code=403, detail="Quota exceeded")
    return await _proxy_to_storage("POST", f"/files/presign?user_id={user['id']}", user)


# =============================================================================
# Job endpoints (proxy to Orchestrator)
# =============================================================================

async def _proxy_to_orchestrator(method: str, path: str, user: dict, json: dict = None):
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


# =============================================================================
# Live transcription — WebSocket (real-time mic streaming)
# =============================================================================

@router.websocket("/ws/live")
async def live_transcription(websocket: WebSocket, token: str = Query(None)):
    """
    Real-time Arabic transcription via WebSocket.
    Client streams audio chunks (webm/opus), server returns partial + final transcripts.

    Flow:
      1. Client connects with ?token=<jwt>
      2. Gateway verifies token
      3. Client sends raw audio bytes in chunks
      4. Gateway pushes chunks to Redis queue for GPU worker
      5. GPU worker transcribes and pushes results back to Redis
      6. Gateway polls results and sends back to client
    """
    await websocket.accept()

    # Verify token
    try:
        if not token:
            await websocket.send_json({"type": "error", "message": "Authentication required"})
            await websocket.close(code=4001)
            return
        payload = decode_token(token)
        user_id = str(payload.get("sub"))
        if not user_id:
            await websocket.send_json({"type": "error", "message": "Invalid token"})
            await websocket.close(code=4001)
            return
    except Exception:
        await websocket.send_json({"type": "error", "message": "Invalid token"})
        await websocket.close(code=4001)
        return

    import redis.asyncio as aioredis
    r = aioredis.from_url(config.REDIS_URL)
    session_id = f"live:{user_id}:{id(websocket)}"
    audio_key = f"live:audio:{session_id}"
    result_key = f"live:result:{session_id}"

    try:
        await websocket.send_json({"type": "connected", "session_id": session_id})

        while True:
            try:
                # Receive audio chunk from client (30s timeout = keepalive)
                message = await asyncio.wait_for(websocket.receive(), timeout=30.0)
            except asyncio.TimeoutError:
                await websocket.send_json({"type": "ping"})
                continue
            except WebSocketDisconnect:
                break

            # Handle close/disconnect
            if message.get("type") == "websocket.disconnect":
                break

            # Handle binary audio data
            if "bytes" in message and message["bytes"]:
                audio_chunk = message["bytes"]
                # Push audio to Redis for GPU worker
                await r.rpush(audio_key, audio_chunk)
                await r.expire(audio_key, 120)
                # Signal worker there's audio to process
                await r.publish(f"live:notify:{session_id}", "chunk")

            # Handle text messages (e.g. {"type": "end"})
            elif "text" in message and message["text"]:
                try:
                    data = json.loads(message["text"])
                    if data.get("type") == "end":
                        await r.publish(f"live:notify:{session_id}", "end")
                except Exception:
                    pass

            # Poll for transcription results from GPU worker
            for _ in range(10):
                result = await r.lpop(result_key)
                if result:
                    await websocket.send_json(json.loads(result))
                else:
                    break

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass
    finally:
        await r.delete(audio_key)
        await r.delete(result_key)
        await r.aclose()


# =============================================================================
# Audio file transcription — WebSocket (upload file, stream results)
# =============================================================================

@router.websocket("/ws/transcribe")
async def file_transcription(websocket: WebSocket, token: str = Query(None)):
    """
    Upload an audio file and stream back transcription results in real time.

    Flow:
      1. Client connects with ?token=<jwt>
      2. Client sends audio file bytes in chunks
      3. Client sends {"type": "end"} when done
      4. Gateway pushes to Redis for GPU worker
      5. Results streamed back as they arrive
    """
    await websocket.accept()

    # Verify token
    try:
        if not token:
            await websocket.send_json({"type": "error", "message": "Authentication required"})
            await websocket.close(code=4001)
            return
        payload = decode_token(token)
        user_id = str(payload.get("sub"))
        if not user_id:
            await websocket.send_json({"type": "error", "message": "Invalid token"})
            await websocket.close(code=4001)
            return
    except Exception:
        await websocket.send_json({"type": "error", "message": "Invalid token"})
        await websocket.close(code=4001)
        return

    import redis.asyncio as aioredis
    r = aioredis.from_url(config.REDIS_URL)
    session_id = f"transcribe:{user_id}:{id(websocket)}"
    audio_key = f"transcribe:audio:{session_id}"
    result_key = f"transcribe:result:{session_id}"

    try:
        await websocket.send_json({"type": "connected", "session_id": session_id})

        upload_done = False
        while not upload_done:
            try:
                message = await asyncio.wait_for(websocket.receive(), timeout=60.0)
            except asyncio.TimeoutError:
                await websocket.send_json({"type": "error", "message": "Upload timeout"})
                break
            except WebSocketDisconnect:
                break

            if message.get("type") == "websocket.disconnect":
                break

            if "bytes" in message and message["bytes"]:
                await r.append(audio_key, message["bytes"])
                await r.expire(audio_key, 300)
                await websocket.send_json({"type": "uploading"})

            elif "text" in message and message["text"]:
                try:
                    data = json.loads(message["text"])
                    if data.get("type") == "end":
                        upload_done = True
                        # Signal GPU worker to process this file
                        await r.rpush("queue:live_transcribe", json.dumps({
                            "session_id": session_id,
                            "audio_key": audio_key,
                            "result_key": result_key,
                            "user_id": user_id,
                        }))
                        await websocket.send_json({"type": "processing"})
                except Exception:
                    pass

        # Stream results back as GPU worker produces them
        if upload_done:
            timeout_count = 0
            while timeout_count < 120:  # max 2 minutes
                result = await r.lpop(result_key)
                if result:
                    data = json.loads(result)
                    await websocket.send_json(data)
                    timeout_count = 0
                    if data.get("type") == "done":
                        break
                else:
                    await asyncio.sleep(0.5)
                    timeout_count += 1

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass
    finally:
        await r.delete(audio_key)
        await r.delete(result_key)
        await r.aclose()
