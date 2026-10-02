import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.auth.dependencies import get_current_user_with_tenant
from app.auth.permissions import require_roles_with_tenant
from app.models.feedback import Answer, AnswerFeedback
from app.models.user import User
from app.schemas.feedback import (
    FeedbackCreate,
    FeedbackUpdate,
    FeedbackResponse,
    AnswerWithFeedback,
    FeedbackListResponse,
)

router = APIRouter(prefix="/answers", tags=["feedback"])


@router.post("/{answer_id}/feedback", response_model=FeedbackResponse, status_code=status.HTTP_201_CREATED)
async def create_feedback(
    answer_id: uuid.UUID,
    feedback_in: FeedbackCreate,
    current_user_tenant: tuple[User, str] = Depends(require_roles_with_tenant("client_admin", "employee")),
    db: AsyncSession = Depends(get_db),
):
    """Submit feedback (thumbs up/down + optional comment) for an answer."""
    current_user, tenant_id = current_user_tenant
    tenant_uuid = uuid.UUID(tenant_id)

    # Verify answer exists and belongs to tenant
    result = await db.execute(
        select(Answer).where(
            Answer.id == answer_id,
            Answer.tenant_id == tenant_uuid
        )
    )
    answer = result.scalar_one_or_none()
    if not answer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Answer not found")

    # Check if user already voted on this answer
    result = await db.execute(
        select(AnswerFeedback).where(
            AnswerFeedback.answer_id == answer_id,
            AnswerFeedback.user_id == current_user.id
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Feedback already exists for this answer from this user. Use PATCH to update."
        )

    feedback = AnswerFeedback(
        tenant_id=tenant_uuid,
        user_id=current_user.id,
        answer_id=answer_id,
        vote=feedback_in.vote,
        comment=feedback_in.comment,
    )
    db.add(feedback)
    await db.commit()
    await db.refresh(feedback)

    return feedback


@router.patch("/{answer_id}/feedback", response_model=FeedbackResponse)
async def update_feedback(
    answer_id: uuid.UUID,
    feedback_in: FeedbackUpdate,
    current_user_tenant: tuple[User, str] = Depends(require_roles_with_tenant("client_admin", "employee")),
    db: AsyncSession = Depends(get_db),
):
    """Update existing feedback (change vote and/or comment)."""
    current_user, tenant_id = current_user_tenant
    tenant_uuid = uuid.UUID(tenant_id)

    result = await db.execute(
        select(AnswerFeedback).where(
            AnswerFeedback.answer_id == answer_id,
            AnswerFeedback.user_id == current_user.id,
            AnswerFeedback.tenant_id == tenant_uuid
        )
    )
    feedback = result.scalar_one_or_none()
    if not feedback:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Feedback not found")

    if feedback_in.vote is not None:
        feedback.vote = feedback_in.vote
    if feedback_in.comment is not None:
        feedback.comment = feedback_in.comment

    from datetime import datetime, timezone
    feedback.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(feedback)

    return feedback


@router.get("/{answer_id}/feedback", response_model=FeedbackResponse)
async def get_feedback(
    answer_id: uuid.UUID,
    current_user_tenant: tuple[User, str] = Depends(require_roles_with_tenant("client_admin", "employee")),
    db: AsyncSession = Depends(get_db),
):
    """Get feedback for a specific answer (only own feedback for employee, all for client_admin)."""
    current_user, tenant_id = current_user_tenant
    tenant_uuid = uuid.UUID(tenant_id)

    # Employee can only see their own feedback
    if current_user.role == "employee":
        result = await db.execute(
            select(AnswerFeedback).where(
                AnswerFeedback.answer_id == answer_id,
                AnswerFeedback.user_id == current_user.id,
                AnswerFeedback.tenant_id == tenant_uuid
            )
        )
    else:
        # Client admin can see all feedback for this answer
        result = await db.execute(
            select(AnswerFeedback).where(
                AnswerFeedback.answer_id == answer_id,
                AnswerFeedback.tenant_id == tenant_uuid
            )
        )

    feedback = result.scalar_one_or_none()
    if not feedback:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Feedback not found")

    return feedback


@router.get("/feedback", response_model=FeedbackListResponse)
async def list_feedback(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    answer_id: Optional[uuid.UUID] = Query(None),
    vote: Optional[int] = Query(None),
    current_user_tenant: tuple[User, str] = Depends(require_roles_with_tenant("client_admin")),
    db: AsyncSession = Depends(get_db),
):
    """List all feedback in tenant (client_admin only). Supports filtering by answer_id and vote."""
    _, tenant_id = current_user_tenant
    tenant_uuid = uuid.UUID(tenant_id)

    offset = (page - 1) * page_size

    query = select(AnswerFeedback).where(AnswerFeedback.tenant_id == tenant_uuid)

    if answer_id:
        query = query.where(AnswerFeedback.answer_id == answer_id)
    if vote is not None:
        query = query.where(AnswerFeedback.vote == vote)

    # Total count
    total_result = await db.execute(
        select(func.count()).select_from(query.subquery())
    )
    total = total_result.scalar() or 0

    # Paginated results
    result = await db.execute(
        query.order_by(AnswerFeedback.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    feedback_list = result.scalars().all()

    return FeedbackListResponse(
        feedback=feedback_list,
        total=total,
        page=page,
        page_size=page_size,
    )