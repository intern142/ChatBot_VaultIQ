from pydantic import BaseModel, Field, ConfigDict
from uuid import UUID
from datetime import datetime
from enum import Enum


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


class TenantResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    short_code: str
    name: str
    status: TenantStatus
    created_at: datetime
    updated_at: datetime
