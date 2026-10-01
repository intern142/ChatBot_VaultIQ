import re
import bcrypt


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


# Matches no real account. Used only to spend the same CPU time on failure paths
# that never reach a real password check, so that a locked account, an unknown
# email and a wrong password all cost the caller the same wall-clock time.
_TIMING_EQUALISER_HASH = hash_password("vaultiq-timing-equaliser")


def burn_password_verification_time(password: str) -> None:
    """Run a bcrypt comparison and discard the result, purely to burn CPU time.

    Callers must not branch on anything here. Its only purpose is to stop response
    time from revealing which login outcome occurred.
    """
    verify_password(password, _TIMING_EQUALISER_HASH)


def validate_password_strength(password: str) -> list[str]:
    errors = []
    if len(password) < 8:
        errors.append("Password must be at least 8 characters")
    if not re.search(r"[A-Z]", password):
        errors.append("Password must contain at least one uppercase letter")
    if not re.search(r"[a-z]", password):
        errors.append("Password must contain at least one lowercase letter")
    if not re.search(r"\d", password):
        errors.append("Password must contain at least one digit")
    if not re.search(r"[!@#$%^&*()_+\-=\[\]{};':\"\\|,.<>\/?]", password):
        errors.append("Password must contain at least one special character")
    return errors
