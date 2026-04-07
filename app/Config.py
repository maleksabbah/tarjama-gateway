"""
Gateway Configuration
Loads all settings from environment variables with sensible defaults.
"""
import os


class Config:
    # Database
    DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:Saras2345%40@localhost:5432/gateway_db")
    DB_POOL_MIN = int(os.getenv("DB_POOL_MIN", "2"))
    DB_POOL_MAX = int(os.getenv("DB_POOL_MAX", "10"))

    # Redis
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    # JWT
    JWT_SECRET = os.getenv("JWT_SECRET", "change-this-in-production")
    JWT_ALGORITHM = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_ACCESS_EXPIRE", "30"))
    JWT_REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("JWT_REFRESH_EXPIRE", "7"))

    # Rate Limiting
    RATE_LIMIT_REQUESTS = int(os.getenv("RATE_LIMIT_REQUESTS", "100"))
    RATE_LIMIT_WINDOW_SECONDS = int(os.getenv("RATE_LIMIT_WINDOW", "60"))
    UPLOAD_RATE_LIMIT = int(os.getenv("UPLOAD_RATE_LIMIT", "10"))
    UPLOAD_RATE_WINDOW = int(os.getenv("UPLOAD_RATE_WINDOW", "3600"))

    # Downstream Services
    ORCHESTRATOR_URL = os.getenv("ORCHESTRATOR_URL", "http://localhost:8001")
    STORAGE_URL = os.getenv("STORAGE_URL", "http://localhost:8002")

    # Server
    HOST = os.getenv("HOST", "0.0.0.0")
    PORT = int(os.getenv("PORT", "8000"))


config = Config()