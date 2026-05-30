from pydantic import BaseModel, EmailStr


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str


class UpdateUsageRequest(BaseModel):
    minutes: float