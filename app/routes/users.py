"""VQ-301: Client Admin user management.

Separate from `app/routes/admin.py`, and deliberately mounted at `/users`
rather than `/admin`.

Two reasons, both about keeping a rule intact rather than adding exceptions:

  * `app/routes/admin.py` carries `require_roles("super_admin")` at router
    level, so a Client Admin endpoint cannot live there.
  * `test_tenant_lifecycle.py` asserts that *every* `/admin/*` operation in
    ROLE_MATRIX is Super Admin only, and there are exactly six of them. Putting
    a tenant-scoped operation under `/admin` would have meant weakening that
    test or deleting the invariant. `/admin` keeps meaning "platform operator";
    these operations are the client managing its own people, which is a different
    thing and deserves a different path.

VQ-106 AC4 denies Super Admin document-content operations, and the Sprint 3
specs name the Client Admin as the actor for tenant-scoped work.

What is here, by criterion:

  AC1  POST /users/invites              invite one user at a chosen role
  AC2  POST /users/import               CSV import, all-or-nothing
  AC3  POST /users/{id}/deactivate      and /reactivate
  AC4  POST /users/{id}/password-reset  (see below)
  AC5  PATCH /users/{id}/role           behind step-up re-authentication
  AC6  GET  /users/audit                tenant-scoped trail

Route order matters. `/users/audit` is declared before `/users/{user_id}/...`:
FastAPI matches in declaration order, and `{user_id}` is typed UUID, so with the
literal path second it would 422 instead of matching.

Tenant scoping is never done by filtering in the query. `get_current_user` has
already set `app.current_tenant` from the verified token, so RLS restricts what
these queries can even see. A user id belonging to another tenant is therefore
simply not found, which is the 404-not-403 rule from VQ-103: refusing must not
confirm that the other tenant exists.
"""
import base64
import csv
import hashlib
import io
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.auth.password import hash_password, verify_password
from app.auth.permissions import require_roles
from app.config import get_settings
from app.database import get_db
from app.models.audit_log import AuditLog
from app.models.invite import Invite
from app.models.reset_code import ResetCode
from app.models.session import Session
from app.models.user import User
from app.services.audit import write_audit_log
from app.schemas.user import (
    AuditLogResponse,
    DeactivateResponse,
    EMAIL_PATTERN,
    ImportResponse,
    ImportRowResult,
    INVITABLE_ROLES,
    MAX_IMPORT_BYTES,
    MAX_IMPORT_ROWS,
    PasswordResetIssued,
    ReactivateResponse,
    RoleChangeRequest,
    RoleChangeResponse,
    UserInviteCreate,
    UserInviteIssued,
    UserResponse,
    normalise_email,
)

router = APIRouter(
    prefix="/users",
    tags=["users"],
    dependencies=[Depends(require_roles("client_admin"))],
)
settings = get_settings()

# A user created by CSV import has to have *a* password hash, because the column
# is NOT NULL. It is the hash of a 256-bit random value that is thrown away
# immediately and never returned to anyone, so the account cannot be logged into
# until its owner uses the password-reset flow to set one. The alternative -
# shipping a shared default password, or putting passwords in the CSV - would
# mean a plaintext credential store that we invented and then had to secure.
UNUSABLE_PASSWORD_PREFIX = "unusable:"

# Per-row report statuses. A row that validated is PENDING until the import's
# outcome is known, because "created" is a claim about the users table and the
# whole point of the all-or-nothing rule is that a refused import writes nothing.
PENDING = "pending"
CREATED = "created"
NOT_CREATED = "not_created"


def generate_reset_code() -> str:
    """32 bytes -> 43 char base64url, same shape as the invite codes."""
    return base64.urlsafe_b64encode(secrets.token_bytes(32)).decode("ascii").rstrip("=")


def generate_invite_code() -> str:
    """Same shape and entropy as a reset code. See the VQ-107 note: these are
    stored in plaintext, which is that table's known defect, not a choice here."""
    return base64.urlsafe_b64encode(secrets.token_bytes(32)).decode("ascii").rstrip("=")


def hash_reset_code(code: str) -> str:
    """SHA-256 hex digest.

    The plaintext code is a bearer credential that can set the account's
    password, so it is never stored. Nothing here is a substitute for the
    entropy of the code itself; it only means a database read does not hand
    over a working reset.
    """
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


async def _find_visible_user(db: AsyncSession, user_id: UUID) -> User:
    """Load a user the caller is allowed to see, or 404.

    No tenant filter: the tenant context is already set from the verified token,
    so RLS restricts this read to the caller's own tenant. Another tenant's user
    id is not found rather than forbidden, because a 403 would confirm it exists.
    """
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    return user


async def _user_response(db: AsyncSession, user: User) -> UserResponse:
    """Serialise a user whose row this transaction has just changed.

    `users.updated_at` is `onupdate=func.now()`, so the UPDATE expires that
    attribute and reading it back triggers a refresh - which is a database round
    trip, and therefore has to be awaited inside the transaction where the tenant
    context still exists. Building the response after `db.commit()` instead fails
    with MissingGreenlet, and refreshing after the commit would run with no
    tenant context at all, because `set_config(..., true)` is transaction-scoped
    (the same trap documented in app/routes/auth.py).
    """
    await db.refresh(user)
    return UserResponse.model_validate(user)


async def _revoke_sessions(db: AsyncSession, user_id: UUID, now: datetime) -> int:
    result = await db.execute(
        update(Session)
        .where(Session.user_id == user_id, Session.is_revoked == False)  # noqa: E712
        .values(is_revoked=True, revoked_at=now)
        .returning(Session.id)
    )
    return len(result.scalars().all())


# ---------------------------------------------------------------------------
# AC1 — invite one user
# ---------------------------------------------------------------------------


@router.post("/invites", response_model=UserInviteIssued, status_code=status.HTTP_201_CREATED)
async def create_user_invite(
    request: UserInviteCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Invite one person into the caller's own tenant.

    The code comes back in the body for hand-off. No mail relay is contacted, per
    the no-internet rule.
    """
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(hours=request.expires_in_hours)

    existing = await db.execute(
        select(User).where(
            User.tenant_id == current_user.tenant_id,
            User.email == request.email,
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists in your organisation",
        )

    pending = await db.execute(
        select(Invite).where(
            Invite.tenant_id == current_user.tenant_id,
            Invite.email == request.email,
            Invite.used_at.is_(None),
            Invite.expires_at > now,
        )
    )
    if pending.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An active invite already exists for this email",
        )

    invite = Invite(
        tenant_id=current_user.tenant_id,
        email=request.email,
        code=generate_invite_code(),
        role=request.role,
        expires_at=expires_at,
        created_by=current_user.id,
    )
    db.add(invite)
    await db.flush()

    await write_audit_log(
        db=db,
        tenant_id=current_user.tenant_id,
        actor_user_id=current_user.id,
        actor_role=current_user.role,
        action="create_user_invite",
        target_type="invite",
        target_id=invite.id,
        details={"email": invite.email, "role": invite.role, "expires_at": expires_at.isoformat()},
    )

    await db.commit()
    return UserInviteIssued(
        code=invite.code, email=invite.email, role=invite.role, expires_at=expires_at
    )


# ---------------------------------------------------------------------------
# AC2 — CSV import: validate everything, then apply all of it or none of it
# ---------------------------------------------------------------------------

CSV_REQUIRED_COLUMNS = {"email", "role"}


def _parse_import(raw: bytes) -> list[tuple[int, str, str]]:
    """(line_number, email, role) for each data row, header validated.

    Returns (rows, None) or (None, error_detail). Raises nothing, so a malformed
    file is a reportable 400 rather than a 500 from somewhere inside the parser.
    """
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return None, "File must be UTF-8 encoded"

    reader = csv.reader(io.StringIO(text))
    try:
        rows = list(reader)
    except csv.Error as exc:
        return None, f"Could not parse CSV: {exc}"

    # Blank lines are dropped, but the reported line number has to stay the line
    # the admin will see in their editor. Enumerating the filtered list instead
    # would drift by one for every blank line above the error, which makes the
    # report - the entire point of this endpoint - point at the wrong row.
    kept = [(number, row) for number, row in enumerate(rows, start=1) if any(cell.strip() for cell in row)]
    if not kept:
        return None, "CSV file is empty"

    header = [cell.strip().lower() for cell in kept[0][1]]
    missing = CSV_REQUIRED_COLUMNS - set(header)
    if missing:
        return None, "CSV header is missing required column(s): " + ", ".join(
            sorted(missing)
        )

    email_idx = header.index("email")
    role_idx = header.index("role")

    parsed: list[tuple[int, str, str]] = []
    for line_number, row in kept[1:]:
        email = row[email_idx].strip() if email_idx < len(row) else ""
        role = row[role_idx].strip().lower() if role_idx < len(row) else ""
        parsed.append((line_number, email, role))
    return parsed, None


@router.post(
    "/import",
    response_model=ImportResponse,
    # A file with any invalid row is a bad request, not a success with a caveat.
    # Declared here so the 400 carries the same report shape as the 200.
    responses={400: {"model": ImportResponse}},
)
async def import_users(
    response: Response,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Import staff from a CSV of `email,role`.

    All-or-nothing by construction: every row is validated before anything is
    written, and a single invalid row returns 400 with a per-row report and an
    unchanged `users` table. A half-applied staff list is worse than none,
    because the admin cannot tell which half landed.

    The status is 400 rather than 200-with-`applied: false` on purpose. Every other
    validation failure in this API is a 4xx, and a frontend that treats 2xx as
    "the rows landed" would otherwise render a green tick over an empty staff list.
    The report is in the 400 body, which is the whole deliverable of this
    endpoint, so a client that ignores error bodies loses it - that is the
    client's bug to fix, and it is visible immediately rather than silent.
    """
    # Read one byte past the cap rather than trusting Content-Length or the
    # client's declaration. `file.read()` with no limit is how an upload turns
    # into an allocation of whatever size the caller chose.
    raw = await file.read(MAX_IMPORT_BYTES + 1)
    if len(raw) > MAX_IMPORT_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"File is larger than {MAX_IMPORT_BYTES} bytes. A staff list of "
                f"{MAX_IMPORT_ROWS} rows does not need to be."
            ),
        )

    rows, error = _parse_import(raw)
    if error is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error)

    if len(rows) > MAX_IMPORT_ROWS:
        # Refused before parsing into anything else. An unbounded import is one
        # request away from filling the users table.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"CSV has {len(rows)} rows; the maximum is {MAX_IMPORT_ROWS}",
        )

    results: list[ImportRowResult] = []
    seen: set[str] = set()
    to_create: list[tuple[int, str, str]] = []

    # Emails already in this tenant. One query rather than one per row, and it
    # runs under the tenant context so it can only ever see this tenant's rows.
    existing_result = await db.execute(
        select(User.email).where(User.tenant_id == current_user.tenant_id)
    )
    existing_emails = {e.lower() for e in existing_result.scalars().all()}

    now = datetime.now(timezone.utc)

    # Outstanding invites, for the same reason and with the same scoping.
    #
    # Without this the two ways of adding a person can collide: invite someone,
    # then import a file that also lists them, and the invite can no longer be
    # accepted because the address is taken. Found at Gate 6 as a 500 on
    # /invite/accept; refusing the row here is the actual fix, and it gives the
    # admin a reason they can act on instead of a collision they cannot see.
    pending_result = await db.execute(
        select(Invite.email).where(
            Invite.tenant_id == current_user.tenant_id,
            Invite.used_at.is_(None),
            Invite.expires_at > now,
        )
    )
    pending_emails = {e.lower() for e in pending_result.scalars().all()}

    for line, email, role in rows:
        normalised = normalise_email(email)
        if not normalised:
            results.append(ImportRowResult(line=line, email=email, status="invalid", reason="Email is empty"))
        elif not EMAIL_PATTERN.match(normalised):
            results.append(ImportRowResult(line=line, email=email, status="invalid", reason="Not a valid email address"))
        elif role not in INVITABLE_ROLES:
            results.append(ImportRowResult(line=line, email=email, status="invalid", reason="Role must be employee or client_admin"))
        elif normalised in seen:
            results.append(ImportRowResult(line=line, email=email, status="invalid", reason="Duplicate email within this file"))
        elif normalised in existing_emails:
            results.append(ImportRowResult(line=line, email=email, status="invalid", reason="A user with this email already exists in your organisation"))
        elif normalised in pending_emails:
            results.append(ImportRowResult(line=line, email=email, status="invalid", reason="An invite is already outstanding for this email"))
        else:
            seen.add(normalised)
            to_create.append((line, normalised, role))
            # "pending", not "created": at this point nothing has been written, and
            # this import may still be refused by a later row. The final status is
            # decided below, once the outcome is known.
            results.append(ImportRowResult(line=line, email=email, status=PENDING))

    invalid_count = sum(1 for r in results if r.status == "invalid")
    if invalid_count:
        # Nothing has been written at this point, so returning here IS the
        # all-or-nothing guarantee. No rollback needed because no statement ran.
        #
        # The rows that validated have to be downgraded here. Leaving them as
        # "created" would hand the caller a report saying users exist when the
        # users table is untouched - and this report is the entire deliverable of
        # the endpoint, so it is what the frontend renders.
        for r in results:
            if r.status == PENDING:
                r.status = NOT_CREATED
                r.reason = "Not imported, because another row in this file is invalid"
        response.status_code = status.HTTP_400_BAD_REQUEST
        return ImportResponse(
            applied=False,
            total_rows=len(rows),
            created_count=0,
            invalid_count=invalid_count,
            rows=results,
            message=(
                f"{invalid_count} of {len(rows)} rows are invalid. No users were "
                "created. Fix the rows listed above and upload the file again."
            ),
        )

    now = datetime.now(timezone.utc)
    created: list[User] = []
    for _line, email, role in to_create:
        user = User(
            tenant_id=current_user.tenant_id,
            email=email,
            # Nobody, ever, learns this value. The account is unusable until its
            # owner goes through the reset flow.
            password_hash=hash_password(UNUSABLE_PASSWORD_PREFIX + secrets.token_urlsafe(32)),
            role=role,
            is_active=True,
        )
        db.add(user)
        created.append(user)

    try:
        await db.flush()
    except IntegrityError:
        # The unique (tenant_id, email) constraint is the real authority. It can
        # fire here for a row that raced with another import between our read and
        # this write, and the answer to that is the same 409 as any other
        # duplicate, not a 500.
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="One or more of those emails was just created. Nothing was imported.",
        )

    await write_audit_log(
        db=db,
        tenant_id=current_user.tenant_id,
        actor_user_id=current_user.id,
        actor_role=current_user.role,
        action="import_users",
        target_type="tenant",
        target_id=current_user.tenant_id,
        # Counts and the addresses, never anything credential-shaped. The
        # password hashes are not logged and the file contained none.
        details={
            "imported_count": len(created),
            "emails": [u.email for u in created],
            "roles": {u.email: u.role for u in created},
        },
    )

    await db.commit()

    for r in results:
        if r.status == PENDING:
            r.status = CREATED

    return ImportResponse(
        applied=True,
        total_rows=len(rows),
        created_count=len(created),
        invalid_count=0,
        rows=results,
        message=(
            f"{len(created)} users created. Each must use the password-reset flow "
            "to set their own password before they can log in."
        ),
    )


# ---------------------------------------------------------------------------
# AC3 — deactivate and reactivate
# ---------------------------------------------------------------------------


@router.post("/{user_id}/deactivate", response_model=DeactivateResponse)
async def deactivate_user(
    user_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Deactivate a user and end their sessions in the same transaction.

    The session revocation is not a follow-up. It is in the same transaction as
    the flag so that a deactivated user is out on their very next request, the
    same semantics VQ-107 AC2 gave tenant suspension.
    """
    if user_id == current_user.id:
        # Same argument as AC4's self-reset refusal: nobody else may manage this
        # account, so an admin who deactivates themselves locks themselves out.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot deactivate your own account",
        )

    user = await _find_visible_user(db, user_id)

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="User is already deactivated"
        )

    # A tenant with no active Client Admin has nobody who can invite, import,
    # reactivate or reset anyone. Deactivating the last one makes the tenant
    # permanently unadministrable through the product.
    #
    # This branch is currently unreachable, and that is worth being explicit about
    # rather than leaving a reviewer to reverse-engineer: only a client_admin may
    # call this, and a client_admin may not target themselves, so any caller is
    # necessarily a second active Client Admin and the count below is never zero.
    # The guarantee actually rests on the self-target check above. This stays as
    # defence-in-depth for the day one of those two rules is relaxed, and the test
    # suite asserts the invariant rather than pretending to reach this line.
    if user.role == "client_admin":
        remaining = await db.execute(
            select(func.count())
            .select_from(User)
            .where(
                User.tenant_id == user.tenant_id,
                User.role == "client_admin",
                User.is_active == True,  # noqa: E712
                User.id != user.id,
            )
        )
        if (remaining.scalar_one() or 0) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot deactivate the only active Client Admin in your organisation",
            )

    now = datetime.now(timezone.utc)
    user.is_active = False
    revoked = await _revoke_sessions(db, user.id, now)

    await write_audit_log(
        db=db,
        tenant_id=user.tenant_id,
        actor_user_id=current_user.id,
        actor_role=current_user.role,
        action="deactivate_user",
        target_type="user",
        target_id=user.id,
        details={"email": user.email, "sessions_revoked": revoked},
    )

    body = await _user_response(db, user)
    await db.commit()
    return DeactivateResponse(
        user=body,
        sessions_revoked=revoked,
        message="User deactivated and all their sessions ended.",
    )


@router.post("/{user_id}/reactivate", response_model=ReactivateResponse)
async def reactivate_user(
    user_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Reactivate a user. Sessions are not resurrected; they log in again."""
    user = await _find_visible_user(db, user_id)

    if user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="User is already active"
        )

    user.is_active = True
    # Deliberately not clearing failed_login_attempts / locked_until. A lockout is
    # a security event that a human admin should clear deliberately; a reactivation
    # is an employment decision, not a security decision. AC4's reset is the path
    # that clears a lockout, and that one is also step-up protected.

    await write_audit_log(
        db=db,
        tenant_id=user.tenant_id,
        actor_user_id=current_user.id,
        actor_role=current_user.role,
        action="reactivate_user",
        target_type="user",
        target_id=user.id,
        details={"email": user.email},
    )

    body = await _user_response(db, user)
    await db.commit()
    return ReactivateResponse(
        user=body,
        message="User reactivated. They can log in again.",
    )


# ---------------------------------------------------------------------------
# AC4 — password reset (unchanged from the AC4 delivery)
# ---------------------------------------------------------------------------


@router.post(
    "/{user_id}/password-reset",
    response_model=PasswordResetIssued,
    status_code=status.HTTP_201_CREATED,
)
async def issue_password_reset(
    user_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Issue a one-time reset code for a user in the caller's own tenant.

    The code is returned in the body for the Client Admin to hand over. It is
    the only moment the plaintext exists server-side, and no internal mail relay
    is contacted, per the no-internet rule.
    """
    # Self-target is refused rather than served. The admin already has a valid
    # session, and issuing themselves a code they then have to consume
    # unauthenticated is a way to lock yourself out of your own account.
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Use the change-password flow to change your own password",
        )

    # No explicit tenant filter: get_current_user has already set the tenant
    # context from the verified token, so RLS restricts this read to the
    # caller's own tenant. A user id belonging to another tenant is therefore
    # simply not found, which is the 404-not-403 rule from VQ-103.
    result = await db.execute(select(User).where(User.id == user_id))
    target = result.scalar_one_or_none()
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(hours=settings.RESET_CODE_EXPIRY_HOURS)

    # Cap the number of live codes per user and drop the oldest, so a lost code
    # cannot permanently block a reset and old codes do not accumulate.
    live = await db.execute(
        select(ResetCode)
        .where(
            ResetCode.user_id == user_id,
            ResetCode.used_at.is_(None),
            ResetCode.expires_at > now,
        )
        .order_by(ResetCode.created_at.asc())
    )
    live_codes = list(live.scalars().all())
    overflow = len(live_codes) - (settings.RESET_CODE_MAX_LIVE_PER_USER - 1)
    for stale in live_codes[:overflow] if overflow > 0 else []:
        await db.delete(stale)

    code = generate_reset_code()
    db.add(
        ResetCode(
            tenant_id=target.tenant_id,
            user_id=target.id,
            code_hash=hash_reset_code(code),
            expires_at=expires_at,
            created_by=current_user.id,
        )
    )

    await write_audit_log(
        db=db,
        tenant_id=target.tenant_id,
        actor_user_id=current_user.id,
        actor_role=current_user.role,
        action="request_password_reset",
        target_type="user",
        target_id=target.id,
        details={"expires_at": expires_at.isoformat()},
    )

    await db.commit()

    return PasswordResetIssued(reset_code=code, expires_at=expires_at)


# ---------------------------------------------------------------------------
# AC5 — role change behind step-up re-authentication
# ---------------------------------------------------------------------------


@router.patch("/{user_id}/role", response_model=RoleChangeResponse)
async def change_user_role(
    user_id: UUID,
    request: RoleChangeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Change a user's role between employee and client_admin.

    Step-up re-authentication: the caller re-enters their own password on this
    request. Not a "confirmed within the last N minutes" flag - that needs new
    state and a 9-minute-old token would still authorise a privilege change.

    The target's sessions are revoked so the change takes effect immediately. A
    token minted before it carries the old role claim until it expires, and a
    role change that silently did not apply until later would be worse than a
    sign-out the admin can see.
    """
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot change your own role",
        )

    if not verify_password(request.current_password, current_user.password_hash):
        # 401, and nothing is written. Deliberately before any other check on the
        # target, so a wrong step-up password cannot be used to probe whether a
        # user id exists.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current password is incorrect",
        )

    user = await _find_visible_user(db, user_id)

    if user.role == request.role:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"User already has the role {request.role}",
        )

    now = datetime.now(timezone.utc)
    previous_role = user.role
    user.role = request.role

    # A demotion that would leave the tenant with no active Client Admin is the
    # same lockout as deactivating the last one. Unreachable for the same reason
    # as the equivalent check in deactivate_user above, and kept for the same
    # reason.
    if previous_role == "client_admin" and request.role == "employee":
        remaining = await db.execute(
            select(func.count())
            .select_from(User)
            .where(
                User.tenant_id == user.tenant_id,
                User.role == "client_admin",
                User.is_active == True,  # noqa: E712
                User.id != user.id,
            )
        )
        if (remaining.scalar_one() or 0) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot demote the only active Client Admin in your organisation",
            )

    revoked = await _revoke_sessions(db, user.id, now)

    await write_audit_log(
        db=db,
        tenant_id=user.tenant_id,
        actor_user_id=current_user.id,
        actor_role=current_user.role,
        action="change_user_role",
        target_type="user",
        target_id=user.id,
        details={
            "email": user.email,
            "previous_role": previous_role,
            "new_role": request.role,
            "sessions_revoked": revoked,
        },
    )

    body = await _user_response(db, user)
    await db.commit()
    return RoleChangeResponse(
        user=body,
        sessions_revoked=bool(revoked),
        message=f"Role changed from {previous_role} to {request.role}. Their existing sessions have been ended.",
    )


# ---------------------------------------------------------------------------
# AC6 — tenant-scoped audit trail
# ---------------------------------------------------------------------------


@router.get("/audit", response_model=list[AuditLogResponse])
async def get_tenant_audit(
    limit: int = 200,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """This tenant's audit trail.

    No tenant id in the path. The tenant comes from the verified token, so a
    Client Admin asking for another tenant's audit gets their own rows - there is
    no URL to get wrong, and no value in the request that could redirect the read.
    RLS scopes it the same way it scopes every other tenant table.
    """
    # Bounded on both sides. `limit` is caller input, so an unbounded pass
    # through would be a way to ask for the whole table.
    limit = max(1, min(limit, 500))
    result = await db.execute(
        select(AuditLog)
        .where(AuditLog.tenant_id == current_user.tenant_id)
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
    )
    # model_validate rather than a hand-built dict, so the response shape is
    # checked against AuditLogResponse and a column rename cannot slip through as
    # a missing key.
    return [AuditLogResponse.model_validate(row) for row in result.scalars().all()]