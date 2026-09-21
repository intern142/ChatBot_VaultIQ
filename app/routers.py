from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from uuid import UUID
from typing import List, Optional

from app.database import get_db
from app.models.user import User
from app.models.tenant import Tenant
from app.schemas.user import UserResponse, UserWithSubordinates, UserUpdate

router = APIRouter(prefix="/tenants", tags=["tenants"])


@router.get("/{tenant_id}/staff", response_model=List[UserResponse])
async def list_active_staff(
    tenant_id: UUID,
    db: AsyncSession = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
):
    """List active employees (staff) for a tenant"""
    tenant = await db.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    stmt = select(User).where(
        User.tenant_id == tenant_id,
        User.role == "employee",
        User.is_active == True,
    ).offset(skip).limit(limit)

    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/{tenant_id}/admins", response_model=List[UserResponse])
async def list_admins(
    tenant_id: UUID,
    db: AsyncSession = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
):
    """List admins (client_admin role) for a tenant"""
    tenant = await db.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    stmt = select(User).where(
        User.tenant_id == tenant_id,
        User.role == "client_admin",
        User.is_active == True,
    ).offset(skip).limit(limit)

    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/{tenant_id}/admins/{admin_id}/subordinates", response_model=UserWithSubordinates)
async def get_admin_with_subordinates(
    tenant_id: UUID,
    admin_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get admin with their direct subordinates"""
    tenant = await db.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    stmt = (
        select(User)
        .options(selectinload(User.subordinates))
        .where(User.id == admin_id, User.tenant_id == tenant_id, User.role == "client_admin")
    )
    result = await db.execute(stmt)
    admin = result.scalar_one_or_none()

    if not admin:
        raise HTTPException(status_code=404, detail="Admin not found")

    return admin


@router.get("/{tenant_id}/users/{user_id}", response_model=UserResponse)
async def get_user(
    tenant_id: UUID,
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get a specific user by ID"""
    stmt = select(User).where(User.id == user_id, User.tenant_id == tenant_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return user


@router.patch("/{tenant_id}/users/{user_id}", response_model=UserResponse)
async def update_user(
    tenant_id: UUID,
    user_id: UUID,
    user_update: UserUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update a user (e.g., change role, manager, active status)"""
    stmt = select(User).where(User.id == user_id, User.tenant_id == tenant_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    update_data = user_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(user, field, value)

    await db.commit()
    await db.refresh(user)
    return user