import uuid
from datetime import datetime, timezone, timedelta
from uuid import UUID
import jwt
from app.config import get_settings

settings = get_settings()


def create_access_token(
    user_id: UUID,
    role: str,
    tenant_id: UUID | None,
    session_id: UUID,
) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "role": role,
        "tenant_id": str(tenant_id) if tenant_id else None,
        "jti": str(session_id),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=settings.JWT_EXPIRATION_HOURS)).timestamp()),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
