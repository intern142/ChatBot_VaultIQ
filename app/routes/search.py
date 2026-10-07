import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.auth.dependencies import get_current_user_with_tenant
from app.auth.permissions import require_roles_with_tenant
from app.models.user import User
from app.schemas.search import (
    SearchRequest,
    SearchResponse,
    SearchResult,
    SuggestRequest,
    SuggestResponse,
)
from app.services.search import hybrid_search, search_suggest, SearchTenantRequiredError

router = APIRouter(prefix="/search", tags=["search"])


@router.post("", response_model=SearchResponse)
async def hybrid_search_endpoint(
    request: SearchRequest,
    current_user_tenant: tuple[User, str] = Depends(require_roles_with_tenant("client_admin", "employee")),
    db: AsyncSession = Depends(get_db),
):
    """
    Hybrid search combining keyword (BM25) and vector similarity.
    Uses Reciprocal Rank Fusion (RRF) to combine scores.
    """
    _, tenant_id_str = current_user_tenant
    tenant_id = uuid.UUID(tenant_id_str)

    try:
        return await hybrid_search(
            db=db,
            tenant_id=tenant_id,
            query=request.query,
            top_k=request.top_k,
            hybrid_weight=request.hybrid_weight,
        )
    except SearchTenantRequiredError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/suggest", response_model=SuggestResponse)
async def search_suggest_endpoint(
    q: str = Query(..., min_length=1, max_length=100),
    limit: int = Query(5, ge=1, le=20),
    current_user_tenant: tuple[User, str] = Depends(require_roles_with_tenant("client_admin", "employee")),
    db: AsyncSession = Depends(get_db),
):
    """
    Autocomplete suggestions based on indexed content.
    Uses tsvector prefix matching.
    """
    _, tenant_id_str = current_user_tenant
    tenant_id = uuid.UUID(tenant_id_str)

    try:
        return await search_suggest(
            db=db,
            tenant_id=tenant_id,
            q=q,
            limit=limit,
        )
    except SearchTenantRequiredError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))