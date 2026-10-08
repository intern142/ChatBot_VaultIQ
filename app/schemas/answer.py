"""VQ-207: Answer engine schemas — retrieval-only, no generative fields.

The response carries no generative-text fields of any kind. Every string
here is either an input question or text extracted from a tenant's own
document chunks.
"""

from typing import List, Optional
from pydantic import BaseModel, Field
import uuid


class AnswerRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=500)
    top_k: int = Field(default=10, ge=1, le=50)
    hybrid_weight: float = Field(default=0.5, ge=0.0, le=1.0)


class SpellCorrection(BaseModel):
    original_term: str
    corrected_term: str


class SpellcheckInfo(BaseModel):
    applied: bool = Field(default=False)
    original: str = Field(default="")
    corrected: str = Field(default="")
    corrections: List[SpellCorrection] = Field(default_factory=list)


class AnswerSource(BaseModel):
    document_id: uuid.UUID
    chunk_index: int
    original_filename: str
    score: float
    excerpt: str


class AnswerResponse(BaseModel):
    question: str
    answer_phrase: str = Field(default="")
    routing: str = Field(default="no_answer")
    confidence: float = Field(default=0.0)
    sources: List[AnswerSource] = Field(default_factory=list)
    followups: List[str] = Field(default_factory=list)
    spellcheck: SpellcheckInfo = Field(default_factory=SpellcheckInfo)
    source_document_id: Optional[uuid.UUID] = None
    source_chunk_index: Optional[int] = None