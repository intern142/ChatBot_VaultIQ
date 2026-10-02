import pytest
import uuid
import psycopg2
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from app.models.tenant import Tenant
from app.models.user import User
from app.config import get_settings

settings = get_settings()


@pytest.mark.asyncio
async def test_create_tenant(db_session: AsyncSession):
    tenant = Tenant(
        short_code="ACME",
        name="Acme Corporation",
        status="active",
        storage_quota_mb=2048,
    )
    db_session.add(tenant)
    await db_session.commit()
    await db_session.refresh(tenant)

    assert tenant.id is not None
    assert tenant.short_code == "ACME"
    assert tenant.name == "Acme Corporation"
    assert tenant.status == "active"


@pytest.mark.asyncio
async def test_create_user_with_tenant(db_session: AsyncSession):
    tenant = Tenant(short_code="ACME", name="Acme Corp", storage_quota_mb=2048)
    db_session.add(tenant)
    await db_session.commit()
    await db_session.refresh(tenant)

    user = User(
        tenant_id=tenant.id,
        email="user@acme.com",
        password_hash="hashed_password_here",
        role="employee",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    assert user.id is not None
    assert user.tenant_id == tenant.id
    assert user.email == "user@acme.com"
    assert user.role == "employee"


@pytest.mark.asyncio
async def test_create_user_without_tenant_fails(db_session: AsyncSession):
    user = User(
        tenant_id=None,
        email="user@test.com",
        password_hash="hashed_password",
        role="employee",
    )
    db_session.add(user)
    with pytest.raises(Exception):
        await db_session.commit()


@pytest.mark.asyncio
async def test_create_user_with_fake_tenant_fails(db_session: AsyncSession):
    fake_tenant_id = uuid.uuid4()
    user = User(
        tenant_id=fake_tenant_id,
        email="user@test.com",
        password_hash="hashed_password",
        role="employee",
    )
    db_session.add(user)
    with pytest.raises(Exception):
        await db_session.commit()


@pytest.mark.asyncio
async def test_super_admin_without_tenant(db_session: AsyncSession):
    user = User(
        tenant_id=None,
        email="admin@vaultiq.com",
        password_hash="hashed_password",
        role="super_admin",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    assert user.id is not None
    assert user.tenant_id is None
    assert user.role == "super_admin"


@pytest.mark.asyncio
async def test_tenant_unique_short_code(db_session: AsyncSession):
    tenant1 = Tenant(short_code="ACME", name="Acme Corp")
    db_session.add(tenant1)
    await db_session.commit()

    tenant2 = Tenant(short_code="ACME", name="Another Acme")
    db_session.add(tenant2)
    with pytest.raises(Exception):
        await db_session.commit()


@pytest.mark.asyncio
async def test_user_unique_email_per_tenant(db_session: AsyncSession):
    tenant = Tenant(short_code="ACME", name="Acme Corp", storage_quota_mb=2048)
    db_session.add(tenant)
    await db_session.commit()
    await db_session.refresh(tenant)

    user1 = User(
        tenant_id=tenant.id,
        email="user@acme.com",
        password_hash="hash1",
        role="employee",
    )
    db_session.add(user1)
    await db_session.commit()

    user2 = User(
        tenant_id=tenant.id,
        email="user@acme.com",
        password_hash="hash2",
        role="employee",
    )
    db_session.add(user2)
    with pytest.raises(Exception):
        await db_session.commit()


def test_rls_blocks_cross_tenant_read():
    admin_url = settings.DATABASE_URL_SYNC
    app_url = settings.DATABASE_URL_SYNC.replace("vaultiq:vaultiq_secret", "vaultiq_app:vaultiq_secret")

    admin_conn = psycopg2.connect(admin_url)
    admin_cur = admin_conn.cursor()
    admin_cur.execute("TRUNCATE users, tenants CASCADE")
    admin_conn.commit()

    admin_cur.execute("INSERT INTO tenants (short_code, name, storage_quota_mb) VALUES (%s, %s, %s) RETURNING id", ("TENANT1", "Tenant One", 2048))
    tenant1_id = admin_cur.fetchone()[0]

    admin_cur.execute("INSERT INTO tenants (short_code, name, storage_quota_mb) VALUES (%s, %s, %s) RETURNING id", ("TENANT2", "Tenant Two", 2048))
    tenant2_id = admin_cur.fetchone()[0]

    admin_cur.execute(
        "INSERT INTO users (tenant_id, email, password_hash, role) VALUES (%s, %s, %s, %s)",
        (str(tenant1_id), "user@tenant1.com", "hash", "employee"),
    )
    admin_conn.commit()
    admin_cur.close()
    admin_conn.close()

    conn = psycopg2.connect(app_url)
    cur = conn.cursor()

    cur.execute("SELECT set_config('app.current_tenant', %s, true)", (str(tenant2_id),))
    cur.execute("SELECT * FROM users WHERE tenant_id IS NOT NULL")
    rows = cur.fetchall()
    assert len(rows) == 0, f"RLS failed: expected 0 rows, got {len(rows)}"
    conn.commit()

    cur.execute("SELECT set_config('app.current_tenant', %s, true)", (str(tenant1_id),))
    cur.execute("SELECT * FROM users WHERE tenant_id IS NOT NULL")
    rows = cur.fetchall()
    assert len(rows) == 1, f"RLS failed: expected 1 row, got {len(rows)}"
    conn.commit()

    cur.close()
    conn.close()
