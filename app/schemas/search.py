from typing import List
from pydantic import BaseModel, Field
import uuid


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)
    top_k: int = Field(default=10, ge=1, le=50)
    hybrid_weight: float = Field(default=0.5, ge=0.0, le=1.0, description="0 = keyword only, 1 = vector only")


class SearchResult(BaseModel):
    document_id: uuid.UUID
    chunk_index: int
    content: str
    score: float
    original_filename: str


class SearchResponse(BaseModel):
    results: List[SearchResult]
    query: str
    total_results: int


class SuggestRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=100)
    limit: int = Field(default=5, ge=1, le=20)


class SuggestResponse(BaseModel):
    suggestions: List[str]