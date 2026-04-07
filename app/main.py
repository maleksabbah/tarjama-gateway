"""
ASR Gateway Service
====================
The public-facing API gateway for the Arabic ASR platform.
Handles authentication, rate limiting, and proxies requests
to the Orchestrator and Storage services.

Run:
  uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.Config import config
from app.Database import init_db, close_db
from app.Rate_limiter import init_redis, close_redis
from app.Routes import router

from fastapi.security import HTTPBearer

security = HTTPBearer()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    # Startup
    print("Starting Gateway...")
    await init_db()
    print("  PostgreSQL connected")
    await init_redis()
    print("  Redis connected")
    print(f"  Orchestrator: {config.ORCHESTRATOR_URL}")
    print(f"  Storage: {config.STORAGE_URL}")
    print("Gateway ready.")

    yield

    # Shutdown
    print("Shutting down Gateway...")
    await close_db()
    await close_redis()
    print("Gateway stopped.")


app = FastAPI(
    title="ASR Gateway",
    description="Arabic Speech Recognition API Gateway",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


# Include routes
app.include_router(router, prefix="/api")


# Health check
@app.get("/health")
async def health():
    return {"status": "ok", "service": "gateway"}


@app.get("/")
async def root():
    return {
        "service": "ASR Gateway",
        "version": "1.0.0",
        "docs": "/docs",
    }