from pydantic import BaseModel, ConfigDict
from uuid import UUID
from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum


class TenantStatus(str, Enum):
    active = "active"
    suspended = "suspended"
    offboarding = "offboarding"
    purged = "purged"


class TenantOverview(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    short_code: str
    name: str
    status: TenantStatus
    user_count: int
    document_count: int
    storage_used_mb: float
    storage_quota_mb: int
    questions_24h: int
    questions_30d: int
    last_activity: Optional[datetime]
    processing_pending: int
    processing_failed: int


class TenantOverviewDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    tenant: TenantOverview
    questions_per_day_30d: List[Dict[str, Any]]
    storage_per_day_30d: List[Dict[str, Any]]
    top_errors_24h: List[Dict[str, Any]]


class PlatformHealth(BaseModel):
    database: Dict[str, Any]
    disk: Dict[str, Any]
    processing: Dict[str, Any]
    no_internet: bool
    error_rate_24h: float


class PlatformStats(BaseModel):
    total_tenants: int
    active_tenants: int
    total_users: int
    total_documents: int
    total_storage_mb: float
    total_questions_24h: int
    total_questions_30d: int