import pytest
import uuid
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.tenant import Tenant
from app.models.user import User


@pytest.mark.asyncio
async def test_create_tenant(db_session: AsyncSession):
    tenant = Tenant(
        short_code="ACME",
        name="Acme Corporation",
        status="active",
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
    tenant = Tenant(short_code="ACME", name="Acme Corp")
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
    tenant2 = Tenant(short_code="ACME", name="Another Acme")
    db_session.add(tenant1)
    await db_session.commit()

    db_session.add(tenant2)
    with pytest.raises(Exception):
        await db_session.commit()


@pytest.mark.asyncio
async def test_user_unique_email_per_tenant(db_session: AsyncSession):
    tenant = Tenant(short_code="ACME", name="Acme Corp")
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


@pytest.mark.asyncio
async def test_rls_blocks_cross_tenant_read(db_session: AsyncSession):
    tenant1 = Tenant(short_code="TENANT1", name="Tenant One")
    tenant2 = Tenant(short_code="TENANT2", name="Tenant Two")
    db_session.add_all([tenant1, tenant2])
    await db_session.commit()
    await db_session.refresh(tenant1)
    await db_session.refresh(tenant2)

    user1 = User(
        tenant_id=tenant1.id,
        email="user@tenant1.com",
        password_hash="hash",
        role="employee",
    )
    db_session.add(user1)
    await db_session.commit()

    await db_session.execute(text(f"SET app.current_tenant = '{tenant2.id}'"))
    result = await db_session.execute(text("SELECT * FROM users"))
    rows = result.fetchall()
    assert len(rows) == 0
