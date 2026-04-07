"""
Gateway Schemas
Pydantic models for request validation and response serialization.
"""

from pydantic import BaseModel,EmailStr
from typing import Optional,List
from datetime import datetime


# =============================================================================
# Auth schemas
# =============================================================================

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str

class LoginRequest(BaseModel):
    email: EmailStr
    password: str
class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
class RefreshRequest(BaseModel):
    refresh_token: str


class UserResponse(BaseModel):
    id: int
    email: str
    api_key: str
    plan: str
    quota_minutes: int
    used_minutes: float
    created_at: datetime

# =============================================================================
# Job schemas (for proxying to Orchestrator)
# =============================================================================


class CreateJobRequest(BaseModel):
    file_path: str
    dialect: Optional[str] = "auto"
    output_type: Optional[str] = "all"  # transcription_only / subtitles / subtitled_video / all
    subtitle_format: Optional[str] = "srt"  # srt / vtt / both
    burn_subtitles: Optional[bool] = False


class JobResponse(BaseModel):
    id: str
    user_id: int
    status: str
    dialect: Optional[str]
    output_type: str
    created_at: datetime
    completed_at: Optional[datetime]
    error: Optional[str]


class JobProgressResponse(BaseModel):
    job_id: str
    status: str
    total_chunks: int
    completed_chunks: int
    failed_chunks: int
    started_at: Optional[str]
class JobListResponse(BaseModel):
    jobs: List[JobResponse]
    total: int

