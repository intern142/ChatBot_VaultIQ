from pydantic import BaseModel
from typing import List, Optional, Any
from datetime import datetime


class OverviewResponse(BaseModel):
    questions_per_day_30d: List[dict] = []
    active_users: int = 0
    answered_count: int = 0
    partial_count: int = 0
    not_found_count: int = 0
    avg_confidence: Optional[float] = None


class PaginatedResponse(BaseModel):
    items: List[dict] = []
    total: int = 0
    limit: int = 50
    offset: int = 0
