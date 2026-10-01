from pydantic import BaseModel, ConfigDict, Field, field_validator
from typing import Optional
from uuid import UUID
from datetime import datetime
import re

from app.schemas.tenant import UserRole

# Deliberately permissive rather than a strict RFC 5322 pattern. Rejecting a
# legitimate address is worse for the admin than accepting one that will turn out
# not to exist: the user finds out when they fail to log in, and can ask for a
# reset, whereas a wrongly-rejected row in a CSV import looks like a system fault.
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s.]+(\.[^@\s.]+)+$")


def normalise_email(raw: str) -> str:
    return raw.strip().lower()


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
    # VQ-301 AC3. Present on every user shape so the frontend never has to infer
    # activeness from the absence of something.
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PasswordResetIssued(BaseModel):
    """Returned to the Client Admin for on-screen hand-off.

    The only time the plaintext code exists outside the user's own screen. It is
    never written to a log line and is not recoverable afterwards, because only
    its SHA-256 digest is stored.
    """

    reset_code: str = Field(..., min_length=1, max_length=100)
    expires_at: datetime


# ---------------------------------------------------------------------------
# VQ-301 AC1: invite one user
# ---------------------------------------------------------------------------

# super_admin is absent by construction, not by accident. Platform accounts are
# not tenant-scoped work, and VQ-106 reserves them for the operator. Allowing it
# here would let a Client Admin mint a super_admin inside their own tenant.
INVITABLE_ROLES = {"employee", "client_admin"}


class UserInviteCreate(BaseModel):
    email: str = Field(..., min_length=1, max_length=255)
    role: str = Field(..., min_length=1, max_length=50)
    expires_in_hours: int = Field(default=168, ge=1, le=720)

    @field_validator("email")
    @classmethod
    def check_email(cls, v: str) -> str:
        email = normalise_email(v)
        if not EMAIL_PATTERN.match(email):
            raise ValueError("Not a valid email address")
        return email

    @field_validator("role")
    @classmethod
    def check_role(cls, v: str) -> str:
        role = v.strip().lower()
        if role not in INVITABLE_ROLES:
            raise ValueError("Role must be one of: " + ", ".join(sorted(INVITABLE_ROLES)))
        return role


class UserInviteIssued(BaseModel):
    """Returned to the Client Admin for hand-off, mirroring PasswordResetIssued."""

    code: str = Field(..., min_length=1, max_length=64)
    email: str
    role: str
    expires_at: datetime


# ---------------------------------------------------------------------------
# VQ-301 AC2: CSV import
# ---------------------------------------------------------------------------

MAX_IMPORT_ROWS = 500

# A 500-row file of `email,role` is well under 100 KB. This cap is not about the
# row limit - it is about `await file.read()`, which pulls the whole upload into
# memory before anything is validated. Without it a single request can ask the app
# to allocate whatever the client chose to send.
MAX_IMPORT_BYTES = 1_048_576


class ImportRowResult(BaseModel):
    line: int
    email: str
    status: str  # "created" | "invalid"
    reason: Optional[str] = None


class ImportResponse(BaseModel):
    # False whenever any row was invalid. This is the all-or-nothing signal: when
    # it is False, `users` is exactly as it was before the request.
    applied: bool
    total_rows: int
    created_count: int
    invalid_count: int
    rows: list[ImportRowResult]
    message: str


# ---------------------------------------------------------------------------
# VQ-301 AC5: role change behind step-up re-authentication
# ---------------------------------------------------------------------------

class RoleChangeRequest(BaseModel):
    role: str = Field(..., min_length=1, max_length=50)
    # The step-up. The caller re-enters their own password on this request; there
    # is no "recently authenticated" window to replay inside.
    current_password: str = Field(..., min_length=1, max_length=128)

    @field_validator("role")
    @classmethod
    def check_role(cls, v: str) -> str:
        role = v.strip().lower()
        if role not in INVITABLE_ROLES:
            raise ValueError(
                "Role must be one of: " + ", ".join(sorted(INVITABLE_ROLES))
            )
        return role


class RoleChangeResponse(BaseModel):
    user: UserResponse
    sessions_revoked: bool
    message: str


# ---------------------------------------------------------------------------
# VQ-301 AC3: deactivate / reactivate
# ---------------------------------------------------------------------------

class DeactivateResponse(BaseModel):
    user: UserResponse
    sessions_revoked: int
    message: str


class ReactivateResponse(BaseModel):
    user: UserResponse
    message: str


# ---------------------------------------------------------------------------
# VQ-301 AC6: the tenant-scoped audit trail
# ---------------------------------------------------------------------------


class AuditLogResponse(BaseModel):
    """One row of `GET /users/audit`.

    Typed rather than `list[dict]`, so a change to the audit table that the
    endpoint does not account for becomes a validation error instead of a
    silently wrong response body.
    """

    id: UUID
    action: str
    actor_user_id: Optional[UUID] = None
    actor_role: str
    target_type: str
    target_id: Optional[UUID] = None
    # default_factory rather than a literal `{}`: a mutable default is the thing
    # the review checklist calls out, and a shared dict across instances is a
    # latent bug even where the framework happens to copy it.
    details: dict = Field(default_factory=dict)
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)