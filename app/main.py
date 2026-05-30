"""
ASR Gateway — public-facing API.
- Authenticates users (JWT / API key)
- Rate-limits and quota-checks
- Proxies to Orchestrator and Storage services
- Terminates WebSockets for live transcription

Run:
  uvicorn app.main:app --host 0.0.0.0 --port 8000
"""
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.Config.Config import config
from app.Config.Database import close_db
from app.Config.Redis import close_redis
from app.ExceptionHandler import register_exception_handlers
from app.Routes import (
    auth_router,
    user_router,
    job_router,
    file_router,
    ws_router,
)


# ─── Lifespan ───────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("Starting Gateway...")
    app.state.http_client = httpx.AsyncClient(timeout=30.0)
    print(f"  Orchestrator: {config.ORCHESTRATOR_URL}")
    print(f"  Storage:      {config.STORAGE_URL}")
    print("Gateway ready.")

    try:
        yield
    finally:
        # Shutdown
        print("Shutting down Gateway...")
        await app.state.http_client.aclose()
        await close_redis()
        await close_db()
        print("Gateway stopped.")


# ─── App ────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Tarjama Gateway",
    description="Arabic Speech Recognition API Gateway",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)

app.include_router(auth_router, prefix="/api")
app.include_router(user_router, prefix="/api")
app.include_router(job_router, prefix="/api")
app.include_router(file_router, prefix="/api")
app.include_router(ws_router)  # /ws/* — no /api prefix


# ─── Health & root ──────────────────────────────────────────────────────

@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "gateway"}


@app.get("/")
async def root() -> dict:
    return {
        "service": "Tarjama Gateway",
        "version": "2.0.0",
        "docs": "/docs",
    }