import uuid
from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy import ARRAY, CheckConstraint, DateTime, ForeignKey, Index, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base


class Answer(Base):
    __tablename__ = 'answers'

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=False
    )
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    confidence: Mapped[Optional[float]] = mapped_column(nullable=True)
    source_document_ids: Mapped[List[uuid.UUID]] = mapped_column(
        ARRAY(UUID(as_uuid=True)), nullable=False, default=list
    )
    source_chunk_ids: Mapped[List[uuid.UUID]] = mapped_column(
        ARRAY(UUID(as_uuid=True)), nullable=False, default=list
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default="now()"
    )

    feedback: Mapped[List['AnswerFeedback']] = relationship(
        'AnswerFeedback', back_populates='answer', cascade='all, delete-orphan'
    )

    __table_args__ = (
        Index('ix_answers_tenant_user_created', 'tenant_id', 'user_id', 'created_at'),
        Index('ix_answers_tenant_created', 'tenant_id', 'created_at'),
    )


class AnswerFeedback(Base):
    __tablename__ = 'answer_feedback'

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=False
    )
    answer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey('answers.id', ondelete='CASCADE'), nullable=False
    )
    vote: Mapped[int] = mapped_column(nullable=False)  # 1 = up, -1 = down
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default="now()"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default="now()", onupdate=lambda: datetime.now(timezone.utc)
    )

    answer: Mapped['Answer'] = relationship('Answer', back_populates='feedback')

    __table_args__ = (
        UniqueConstraint('answer_id', 'user_id', name='uq_feedback_answer_user'),
        CheckConstraint('vote IN (1, -1)', name='ck_feedback_vote'),
        Index('ix_answer_feedback_tenant_user', 'tenant_id', 'user_id'),
        Index('ix_answer_feedback_tenant_answer', 'tenant_id', 'answer_id'),
    )