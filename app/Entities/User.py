from datetime import datetime
from sqlalchemy import Boolean, Float, Integer, String, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from app.Entities.Base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    api_key: Mapped[str | None] = mapped_column(String(255), unique=True, index=True)
    plan: Mapped[str] = mapped_column(String(50), default="free")
    quota_minutes: Mapped[int] = mapped_column(Integer, default=60)
    used_minutes: Mapped[float] = mapped_column(Float, default=0.0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )