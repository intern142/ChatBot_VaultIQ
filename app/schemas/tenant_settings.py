import re
from pydantic import BaseModel, Field, ConfigDict, field_validator
from uuid import UUID
from datetime import datetime
from typing import Optional, List, Any


# System-wide allowed MIME types (from VQ-201)
SYSTEM_ALLOWED_FORMATS = [
    "application/pdf",
    "text/plain",
    "text/markdown",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "text/csv",
    "application/msword",
    "application/vnd.ms-excel",
    "application/vnd.oasis.opendocument.text",
    "application/vnd.oasis.opendocument.spreadsheet",
    "application/epub+zip",
    "message/rfc822",
    "image/png",
    "image/jpeg",
    "image/tiff",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "application/vnd.ms-powerpoint",
    "application/vnd.oasis.opendocument.presentation",
    "application/x-ole-storage",
]


class TenantSettingsUpdateClientAdmin(BaseModel):
    """Client Admin can update these settings (no storage_quota_mb)"""
    display_name: Optional[str] = Field(None, min_length=1, max_length=255)
    logo_path: Optional[str] = Field(None, max_length=500)
    accent_colour: Optional[str] = Field(None, pattern=r"^#([A-Fa-f0-9]{6}|[A-Fa-f0-9]{3})$")
    not_found_message: Optional[str] = Field(None, max_length=500)
    allowed_upload_formats: Optional[List[str]] = Field(None, min_length=1, max_length=50)
    conversation_retention_days: Optional[int] = Field(None, ge=1, le=3650)

    @field_validator("allowed_upload_formats")
    @classmethod
    def validate_formats(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        if v is None:
            return v
        for fmt in v:
            if fmt not in SYSTEM_ALLOWED_FORMATS:
                raise ValueError(f"Format not allowed: {fmt}")
        return v

    @field_validator("not_found_message")
    @classmethod
    def validate_message(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        # Reject HTML/markdown - must be plain text
        if re.search(r"[<>&]", v):
            raise ValueError("Not found message must be plain text (no HTML/markup)")
        return v


class TenantSettingsUpdateSuperAdmin(TenantSettingsUpdateClientAdmin):
    """Super Admin can also update storage_quota_mb"""
    storage_quota_mb: Optional[int] = Field(None, ge=0)


class TenantSettingsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    tenant_id: UUID
    display_name: Optional[str]
    logo_path: Optional[str]
    accent_colour: Optional[str]
    not_found_message: Optional[str]
    allowed_upload_formats: Optional[List[str]]
    conversation_retention_days: Optional[int]
    updated_by: Optional[UUID]
    updated_at: datetime


class TenantPublicResponse(BaseModel):
    """Public lookup by organisation code - returns only name, logo, colour"""
    name: str
    logo_path: Optional[str]
    accent_colour: Optional[str]


class LogoUploadResponse(BaseModel):
    path: str
    size_bytes: int
    mime_type: str