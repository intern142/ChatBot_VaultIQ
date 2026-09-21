from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime
from typing import Optional, List
from app.schemas.tenant import UserRole


class UserCreate(BaseModel):
    tenant_id: UUID | None = None
    email: str = Field(..., min_length=1, max_length=255)
    password: str = Field(..., min_length=8)
    role: UserRole
    manager_id: Optional[UUID] = None


class UserUpdate(BaseModel):
    email: Optional[str] = Field(None, min_length=1, max_length=255)
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None
    manager_id: Optional[UUID] = None


class UserResponse(BaseModel):
    id: UUID
    tenant_id: UUID | None
    email: str
    role: UserRole
    is_active: bool
    manager_id: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class UserWithSubordinates(UserResponse):
    subordinates: List["UserResponse"] = []


UserWithSubordinates.model_rebuild()
