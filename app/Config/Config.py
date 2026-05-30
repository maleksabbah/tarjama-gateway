"""
Gateway app-wide config.
Reads from environment variables.
"""
import os


class Config:
    # Postgres
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql://postgres:postgres@postgres:5432/gateway_db",
    )
    DB_POOL_MIN: int = int(os.getenv("DB_POOL_MIN", "2"))
    DB_POOL_MAX: int = int(os.getenv("DB_POOL_MAX", "10"))

    # Redis (rate limits)
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://redis:6379/0")

    # JWT
    JWT_SECRET: str = os.getenv("JWT_SECRET", "change-this-in-production")
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("JWT_ACCESS_EXPIRE", "30"))
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = int(os.getenv("JWT_REFRESH_EXPIRE", "7"))

    # Rate limiting
    RATE_LIMIT_REQUESTS: int = int(os.getenv("RATE_LIMIT_REQUESTS", "100"))
    RATE_LIMIT_WINDOW_SECONDS: int = int(os.getenv("RATE_LIMIT_WINDOW", "60"))
    UPLOAD_RATE_LIMIT: int = int(os.getenv("UPLOAD_RATE_LIMIT", "10"))
    UPLOAD_RATE_WINDOW: int = int(os.getenv("UPLOAD_RATE_WINDOW", "3600"))

    # Downstream services
    ORCHESTRATOR_URL: str = os.getenv("ORCHESTRATOR_URL", "http://orchestrator:8001")
    STORAGE_URL: str = os.getenv("STORAGE_URL", "http://storage:8002")

    # Server
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))


config = Config()