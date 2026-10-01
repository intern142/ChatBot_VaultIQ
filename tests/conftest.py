import asyncio
import os
import sys

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import pytest
import pytest_asyncio
import psycopg2
import uuid
import io
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import NullPool
from sqlalchemy import text
from httpx import AsyncClient, ASGITransport
from app.config import get_settings
from app.database import get_db
from app.auth.password import hash_password
from app.auth.jwt import create_access_token
from app.main import app

settings = get_settings()

# Two distinct database identities are used by the test suite:
#
#   ADMIN_DATABASE_URL - the migration/DDL identity (local dev: the `vaultiq`
#       superuser). Used ONLY to truncate and seed fixtures. It has BYPASSRLS
#       so it can see every row, which is exactly what we do not want the
#       application to be able to do.
#
#   APP_DATABASE_URL - the identity the application under test actually uses.
#       Defaults to `vaultiq_app`, which is NOBYPASSRLS, so every request the
#       suite makes has row-level security genuinely enforced.
#
# The default must be the NOBYPASSRLS role. Running the suite against the
# superuser silently disables every RLS policy and makes the whole tenant
# isolation suite meaningless.

ADMIN_DATABASE_URL = os.environ.get("ADMIN_DATABASE_URL", settings.DATABASE_URL)
APP_DATABASE_URL = os.environ.get(
    "APP_DATABASE_URL",
    ADMIN_DATABASE_URL.replace("vaultiq:vaultiq_secret", "vaultiq_app:vaultiq_secret"),
)

test_app_engine = create_async_engine(
    APP_DATABASE_URL,
    echo=False,
    poolclass=NullPool,
)
test_app_session_factory = async_sessionmaker(
    test_app_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def override_get_db():
    async with test_app_session_factory() as session:
        yield session


@pytest.fixture(autouse=True)
def use_test_app_database():
    missing = object()
    previous = app.dependency_overrides.get(get_db, missing)
    app.dependency_overrides[get_db] = override_get_db
    yield
    if previous is missing:
        app.dependency_overrides.pop(get_db, None)
    else:
        app.dependency_overrides[get_db] = previous


@pytest.fixture(scope="session")
def event_loop():
    """Single event loop for the whole suite.

    The app creates a module-level async engine (app.database). Routing each
    test through its own event loop means the pool can hand a connection bound
    to a previously-closed loop to a later test (asyncpg flakes). A shared
    session loop keeps every pooled connection on a live loop.
    """
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="function")
def db_conn():
    conn = psycopg2.connect(settings.DATABASE_URL_SYNC)
    conn.autocommit = False
    cur = conn.cursor()
    cur.execute("TRUNCATE users, tenants, sessions, documents, invites, audit_logs CASCADE")
    conn.commit()
    yield conn
    conn.close()


@pytest.fixture(scope="function")
def app_db_conn():
    """Sync connection as vaultiq_app role (no BYPASSRLS) for RLS testing."""
    app_url = settings.DATABASE_URL_SYNC.replace("vaultiq:vaultiq_secret", "vaultiq_app:vaultiq_secret")
    conn = psycopg2.connect(app_url)
    conn.autocommit = False
    yield conn
    conn.close()


@pytest.fixture(scope="function")
async def db_engine():
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=False,
        pool_pre_ping=True,
    )
    # Truncate at start of each test function
    async with engine.begin() as conn:
        await conn.execute(text("TRUNCATE users, tenants, sessions, documents, invites, audit_logs CASCADE"))
    yield engine
    await engine.dispose()


@pytest.fixture(scope="function")
async def db_session(db_engine):
    session_factory = async_sessionmaker(
        db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with session_factory() as session:
        yield session


@pytest.fixture(scope="function")
async def app_db_engine():
    """Engine connected as vaultiq_app role (no BYPASSRLS)."""
    app_url = settings.DATABASE_URL.replace("vaultiq:vaultiq_secret", "vaultiq_app:vaultiq_secret")
    engine = create_async_engine(
        app_url,
        echo=False,
        pool_pre_ping=True,
    )
    yield engine
    await engine.dispose()


@pytest.fixture(scope="function")
async def app_db_session(app_db_engine):
    """Async session as vaultiq_app role - RLS enforced."""
    admin_engine = create_async_engine(
        settings.DATABASE_URL,
        echo=False,
        pool_pre_ping=True,
    )
    async with admin_engine.begin() as conn:
        await conn.execute(text("TRUNCATE users, tenants, sessions CASCADE"))
    await admin_engine.dispose()
    session_factory = async_sessionmaker(
        app_db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with session_factory() as session:
        yield session


# ---- Isolation suite fixtures ----

@pytest_asyncio.fixture(scope="function")
async def async_client():
    """Test client.

    In-process ASGI transport by default. When LIVE_BASE_URL is set (Gate 6
    live-container verification), use a real HTTP client against the running
    server so the exact suite CI runs also exercises the live container.
    """
    base_url = os.environ.get("LIVE_BASE_URL")
    if base_url:
        async with AsyncClient(base_url=base_url) as ac:
            yield ac
    else:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
            yield ac


@pytest_asyncio.fixture(scope="function")
async def tenant_a(db_engine):
    """Create tenant A with client_admin and employee users + sessions."""
    async with db_engine.begin() as conn:
        result = await conn.execute(text("""
            INSERT INTO tenants (short_code, name, status, storage_quota_mb)
            VALUES ('TENANT_A', 'Tenant A', 'active', 2048)
            RETURNING id
        """))
        tid = result.scalar()
        ph = hash_password("StrongPass1!")
        result = await conn.execute(text("""
            INSERT INTO users (tenant_id, email, password_hash, role)
            VALUES (:tid, 'admin@a.com', :ph, 'client_admin'),
                   (:tid, 'emp@a.com', :ph, 'employee')
            RETURNING id, email, role
        """), {"tid": tid, "ph": ph})
        users = result.mappings().all()
        admin_uid = users[0]["id"]
        emp_uid = users[1]["id"]
        admin_sid = uuid.uuid4()
        emp_sid = uuid.uuid4()
        await conn.execute(text("""
            INSERT INTO sessions (id, user_id, tenant_id, token_hash, expires_at)
            VALUES (:sid1, :uid1, :tid, '', now() + interval '24 hours'),
                   (:sid2, :uid2, :tid, '', now() + interval '24 hours')
        """), {"sid1": admin_sid, "uid1": admin_uid, "sid2": emp_sid, "uid2": emp_uid, "tid": tid})
    return {
        "id": tid,
        "client_admin": {"id": admin_uid, "email": users[0]["email"], "role": users[0]["role"], "session_id": admin_sid},
        "employee": {"id": emp_uid, "email": users[1]["email"], "role": users[1]["role"], "session_id": emp_sid},
    }


@pytest_asyncio.fixture(scope="function")
async def tenant_b(db_engine):
    """Create tenant B with client_admin and employee users + sessions."""
    async with db_engine.begin() as conn:
        result = await conn.execute(text("""
            INSERT INTO tenants (short_code, name, status, storage_quota_mb)
            VALUES ('TENANT_B', 'Tenant B', 'active', 2048)
            RETURNING id
        """))
        tid = result.scalar()
        ph = hash_password("StrongPass1!")
        result = await conn.execute(text("""
            INSERT INTO users (tenant_id, email, password_hash, role)
            VALUES (:tid, 'admin@b.com', :ph, 'client_admin'),
                   (:tid, 'emp@b.com', :ph, 'employee')
            RETURNING id, email, role
        """), {"tid": tid, "ph": ph})
        users = result.mappings().all()
        admin_uid = users[0]["id"]
        emp_uid = users[1]["id"]
        admin_sid = uuid.uuid4()
        emp_sid = uuid.uuid4()
        await conn.execute(text("""
            INSERT INTO sessions (id, user_id, tenant_id, token_hash, expires_at)
            VALUES (:sid1, :uid1, :tid, '', now() + interval '24 hours'),
                   (:sid2, :uid2, :tid, '', now() + interval '24 hours')
        """), {"sid1": admin_sid, "uid1": admin_uid, "sid2": emp_sid, "uid2": emp_uid, "tid": tid})
    return {
        "id": tid,
        "client_admin": {"id": admin_uid, "email": users[0]["email"], "role": users[0]["role"], "session_id": admin_sid},
        "employee": {"id": emp_uid, "email": users[1]["email"], "role": users[1]["role"], "session_id": emp_sid},
    }


@pytest.fixture
def token_a_admin(tenant_a):
    u = tenant_a["client_admin"]
    return create_access_token(
        user_id=u["id"],
        role=u["role"],
        tenant_id=tenant_a["id"],
        session_id=u["session_id"],
    )


@pytest.fixture
def token_a_emp(tenant_a):
    u = tenant_a["employee"]
    return create_access_token(
        user_id=u["id"],
        role=u["role"],
        tenant_id=tenant_a["id"],
        session_id=u["session_id"],
    )


@pytest.fixture
def token_b_admin(tenant_b):
    u = tenant_b["client_admin"]
    return create_access_token(
        user_id=u["id"],
        role=u["role"],
        tenant_id=tenant_b["id"],
        session_id=u["session_id"],
    )


@pytest.fixture
def token_b_emp(tenant_b):
    u = tenant_b["employee"]
    return create_access_token(
        user_id=u["id"],
        role=u["role"],
        tenant_id=tenant_b["id"],
        session_id=u["session_id"],
    )


@pytest_asyncio.fixture(scope="function")
async def super_admin_token(db_conn, db_engine):
    # Both db_conn and db_engine truncate on setup. Requesting both here forces
    # both truncates to happen before this fixture seeds, so a test that also
    # asks for db_conn cannot truncate the super admin row away afterwards.
    async with db_engine.begin() as conn:
        result = await conn.execute(text("""
            INSERT INTO users (tenant_id, email, password_hash, role)
            VALUES (NULL, 'super@vaultiq.com', :ph, 'super_admin')
            RETURNING id
        """), {"ph": hash_password("AdminPass1!")})
        uid = result.scalar()
        sid = uuid.uuid4()
        await conn.execute(text("""
            INSERT INTO sessions (id, user_id, tenant_id, token_hash, expires_at)
            VALUES (:sid, :uid, NULL, '', now() + interval '24 hours')
        """), {"sid": sid, "uid": uid})
    return create_access_token(
        user_id=uid,
        role="super_admin",
        tenant_id=None,
        session_id=sid,
    )


# Aliases for test compatibility
@pytest.fixture
def app_session(app_db_session):
    """Alias for app_db_session - some tests use 'app_session' fixture name."""
    return app_db_session


@pytest.fixture
def token_a(token_a_admin):
    """Alias for token_a_admin - some tests use 'token_a' fixture name."""
    return token_a_admin


@pytest_asyncio.fixture(scope="function")
async def doc_a(async_client, token_a_admin):
    """Upload a document for tenant A."""
    file_content = b"Tenant A document content"
    files = {"file": ("test_a.txt", io.BytesIO(file_content), "text/plain")}
    headers = {"Authorization": f"Bearer {token_a_admin}"}
    resp = await async_client.post("/documents", files=files, headers=headers)
    assert resp.status_code == 201
    return resp.json()


@pytest_asyncio.fixture(scope="function")
async def doc_b(async_client, token_b_admin):
    """Upload a document for tenant B."""
    file_content = b"Tenant B document content"
    files = {"file": ("test_b.txt", io.BytesIO(file_content), "text/plain")}
    headers = {"Authorization": f"Bearer {token_b_admin}"}
    resp = await async_client.post("/documents", files=files, headers=headers)
    assert resp.status_code == 201
    return resp.json()


@pytest_asyncio.fixture(scope="function")
async def invite_code_a(async_client, super_admin_token):
    """Create a fresh tenant (no client admin yet) plus a valid invite for it."""
    headers = {"Authorization": f"Bearer {super_admin_token}"}
    resp = await async_client.post(
        "/admin/tenants",
        json={"short_code": "INVTA", "name": "Invite Tenant A", "storage_quota_mb": 2048},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    tenant_id = resp.json()["id"]
    resp = await async_client.post(
        f"/admin/tenants/{tenant_id}/invite",
        json={"email": "newadmin@invta.com", "expires_in_hours": 168},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return {"tenant_id": tenant_id, "code": resp.json()["code"]}


@pytest_asyncio.fixture(scope="function")
async def invite_code_b(async_client, super_admin_token):
    """Create a fresh tenant (no client admin yet) plus a valid invite for it."""
    headers = {"Authorization": f"Bearer {super_admin_token}"}
    resp = await async_client.post(
        "/admin/tenants",
        json={"short_code": "INVTB", "name": "Invite Tenant B", "storage_quota_mb": 2048},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    tenant_id = resp.json()["id"]
    resp = await async_client.post(
        f"/admin/tenants/{tenant_id}/invite",
        json={"email": "newadmin@invtb.com", "expires_in_hours": 168},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return {"tenant_id": tenant_id, "code": resp.json()["code"]}