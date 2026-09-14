from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime
from app.schemas.tenant import UserRole


class UserCreate(BaseModel):
    tenant_id: UUID | None = None
    email: str = Field(..., min_length=1, max_length=255)
    password: str = Field(..., min_length=8)
    role: UserRole


class UserResponse(BaseModel):
    id: UUID
    tenant_id: UUID | None
    email: str
    role: UserRole
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
