from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime
from app.schemas.tenant import TenantStatus, UserRole


class LoginRequest(BaseModel):
    organisation_code: str = Field(..., min_length=1, max_length=50)
    email: str = Field(..., min_length=1, max_length=255)
    password: str = Field(..., min_length=1)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: UserRole
    tenant_id: UUID | None


class RefreshRequest(BaseModel):
    pass


class MessageResponse(BaseModel):
    detail: str
