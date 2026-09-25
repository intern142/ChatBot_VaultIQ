import re
from pydantic import BaseModel, Field, ConfigDict, EmailStr, field_validator
from uuid import UUID
from datetime import datetime
from enum import Enum
from typing import Optional, Any


class TenantStatus(str, Enum):
    active = "active"
    suspended = "suspended"
    offboarding = "offboarding"
    purged = "purged"


class UserRole(str, Enum):
    super_admin = "super_admin"
    client_admin = "client_admin"
    employee = "employee"


class TenantCreate(BaseModel):
    short_code: str = Field(..., min_length=1, max_length=50)
    name: str = Field(..., min_length=1, max_length=255)
    storage_quota_mb: Optional[int] = Field(None, ge=0)

    @field_validator("short_code")
    @classmethod
    def validate_short_code(cls, v: str) -> str:
        code = v.strip().upper()
        if not re.fullmatch(r"[A-Z0-9]{2,20}", code):
            raise ValueError(
                "Short code must be 2-20 characters: uppercase letters and digits only"
            )
        return code


class TenantResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    short_code: str
    name: str
    status: TenantStatus
    storage_quota_mb: Optional[int]
    created_at: datetime
    updated_at: datetime


class TenantListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    short_code: str
    name: str
    status: TenantStatus
    storage_quota_mb: Optional[int]
    created_at: datetime
    updated_at: datetime


class TenantSuspendRequest(BaseModel):
    pass  # No body needed, just the path param


class TenantReactivateRequest(BaseModel):
    pass  # No body needed, just the path param


class InviteCreate(BaseModel):
    email: EmailStr = Field(..., max_length=255)
    expires_in_hours: Optional[int] = Field(168, ge=1, le=8760)  # Default 7 days, max 1 year


class InviteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    email: str
    code: str
    expires_at: datetime
    used_at: Optional[datetime]
    created_by: UUID
    created_at: datetime


class InviteAcceptRequest(BaseModel):
    code: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=8, max_length=128)


class InviteAcceptResponse(BaseModel):
    detail: str
    tenant_id: UUID
    user_id: UUID


class AuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    actor_user_id: Optional[UUID]
    actor_role: str
    action: str
    target_type: str
    target_id: UUID
    details: dict[str, Any]
    created_at: datetime
