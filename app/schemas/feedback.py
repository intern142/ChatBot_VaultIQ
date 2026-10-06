from typing import List, Optional
from pydantic import BaseModel, Field, field_validator
import uuid
from datetime import datetime


class FeedbackCreate(BaseModel):
    vote: int = Field(..., description="1 for thumbs up, -1 for thumbs down")
    comment: Optional[str] = Field(None, max_length=500)

    @field_validator("vote")
    @classmethod
    def validate_vote(cls, v: int) -> int:
        if v not in (1, -1):
            raise ValueError("vote must be 1 (thumbs up) or -1 (thumbs down)")
        return v


class FeedbackUpdate(BaseModel):
    vote: Optional[int] = Field(None, description="1 for thumbs up, -1 for thumbs down")
    comment: Optional[str] = Field(None, max_length=500)

    @field_validator("vote")
    @classmethod
    def validate_vote(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v not in (1, -1):
            raise ValueError("vote must be 1 (thumbs up) or -1 (thumbs down)")
        return v


class FeedbackResponse(BaseModel):
    id: uuid.UUID
    answer_id: uuid.UUID
    user_id: uuid.UUID
    vote: int
    comment: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AnswerResponse(BaseModel):
    id: uuid.UUID
    question: str
    answer_text: Optional[str]
    confidence: Optional[float]
    source_document_ids: List[uuid.UUID]
    source_chunk_ids: List[uuid.UUID]
    created_at: datetime

    model_config = {"from_attributes": True}


class AnswerWithFeedback(BaseModel):
    answer: AnswerResponse
    feedback: Optional[FeedbackResponse] = None

    model_config = {"from_attributes": True}


class FeedbackListResponse(BaseModel):
    feedback: List[FeedbackResponse]
    total: int
    page: int
    page_size: int