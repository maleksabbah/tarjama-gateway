from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    api_key: Optional[str]
    plan: str
    quota_minutes: int
    used_minutes: float
    created_at: datetime


class QuotaResponse(BaseModel):
    has_quota: bool
    remaining: float
    quota: int
    used: float