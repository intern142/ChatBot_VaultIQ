import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.auth.dependencies import get_current_user_with_tenant
from app.auth.permissions import require_roles_with_tenant
from app.models.document import Document
from app.models.search import DocumentChunk
from app.models.user import User
from app.schemas.search import (
    SearchRequest,
    SearchResponse,
    SearchResult,
    SuggestRequest,
    SuggestResponse,
)

router = APIRouter(prefix="/search", tags=["search"])


@router.post("", response_model=SearchResponse)
async def hybrid_search(
    request: SearchRequest,
    current_user_tenant: tuple[User, str] = Depends(require_roles_with_tenant("client_admin", "employee")),
    db: AsyncSession = Depends(get_db),
):
    """
    Hybrid search combining keyword (BM25) and vector similarity.
    Uses Reciprocal Rank Fusion (RRF) to combine scores.
    """
    _, tenant_id = current_user_tenant
    tenant_uuid = uuid.UUID(tenant_id)

    query = request.query.strip()
    top_k = request.top_k
    hybrid_weight = request.hybrid_weight  # 0 = keyword only, 1 = vector only

    # Generate query embedding
    from app.services.embeddings import embed_text
    query_embedding = embed_text(query)

    # RRF constant
    k = 60

    # Keyword search (BM25 via tsvector)
    keyword_sql = text("""
        SELECT 
            dc.id,
            dc.document_id,
            dc.chunk_index,
            dc.content,
            d.original_filename,
            ts_rank_cd(dc.content_tsv, plainto_tsquery('english', :query)) as bm25_score
        FROM document_chunks dc
        JOIN documents d ON d.id = dc.document_id
        WHERE dc.tenant_id = :tenant_id
          AND dc.content_tsv @@ plainto_tsquery('english', :query)
        ORDER BY bm25_score DESC
        LIMIT :limit
    """)

    keyword_result = await db.execute(
        keyword_sql,
        {"tenant_id": tenant_uuid, "query": query, "limit": top_k * 2}
    )
    keyword_rows = keyword_result.mappings().all()

    # Vector search (cosine similarity)
    vector_sql = text("""
        SELECT 
            dc.id,
            dc.document_id,
            dc.chunk_index,
            dc.content,
            d.original_filename,
            1 - (dc.embedding <=> :embedding) as vector_score
        FROM document_chunks dc
        JOIN documents d ON d.id = dc.document_id
        WHERE dc.tenant_id = :tenant_id
          AND dc.embedding IS NOT NULL
        ORDER BY dc.embedding <=> :embedding
        LIMIT :limit
    """)

    vector_result = await db.execute(
        vector_sql,
        {"tenant_id": tenant_uuid, "embedding": query_embedding, "limit": top_k * 2}
    )
    vector_rows = vector_result.mappings().all()

    # Combine using RRF
    scores = {}  # chunk_id -> (rrf_score, row_data)

    # Add keyword scores
    for rank, row in enumerate(keyword_rows, 1):
        chunk_id = row['id']
        rrf_score = 1.0 / (k + rank)
        scores[chunk_id] = (rrf_score * (1 - hybrid_weight), row)

    # Add vector scores
    for rank, row in enumerate(vector_rows, 1):
        chunk_id = row['id']
        rrf_score = 1.0 / (k + rank)
        if chunk_id in scores:
            scores[chunk_id] = (
                scores[chunk_id][0] + rrf_score * hybrid_weight,
                scores[chunk_id][1]
            )
        else:
            scores[chunk_id] = (rrf_score * hybrid_weight, row)

    # Sort by combined score
    sorted_results = sorted(scores.items(), key=lambda x: x[0], reverse=True)[:top_k]

    results = [
        SearchResult(
            document_id=row['document_id'],
            chunk_index=row['chunk_index'],
            content=row['content'][:500],  # Truncate for response
            score=round(score, 4),
            original_filename=row['original_filename'],
        )
        for score, row in sorted_results
    ]

    return SearchResponse(
        results=results,
        query=query,
        total_results=len(results),
    )


@router.get("/suggest", response_model=SuggestResponse)
async def search_suggest(
    q: str = Query(..., min_length=1, max_length=100),
    limit: int = Query(5, ge=1, le=20),
    current_user_tenant: tuple[User, str] = Depends(require_roles_with_tenant("client_admin", "employee")),
    db: AsyncSession = Depends(get_db),
):
    """
    Autocomplete suggestions based on indexed content.
    Uses tsvector prefix matching.
    """
    _, tenant_id = current_user_tenant
    tenant_uuid = uuid.UUID(tenant_id)

    sql = text("""
        SELECT DISTINCT 
            ts_headline('english', dc.content, plainto_tsquery('english', :query), 
                       'StartSel=, StopSel=, MaxWords=5, MinWords=2') as highlight
        FROM document_chunks dc
        WHERE dc.tenant_id = :tenant_id
          AND dc.content_tsv @@ phraseto_tsquery('english', :query)
        LIMIT :limit
    """)

    result = await db.execute(
        sql,
        {"tenant_id": tenant_uuid, "query": q, "limit": limit}
    )
    rows = result.mappings().all()

    # Extract unique words/phrases from highlights
    suggestions = []
    for row in rows:
        if row['highlight']:
            # Simple extraction - in production, use a proper suggester
            words = row['highlight'].split()
            for w in words:
                clean = w.strip('.,!?()[]{}"\'')
                if len(clean) > 2 and clean.lower() not in [s.lower() for s in suggestions]:
                    suggestions.append(clean)
                    if len(suggestions) >= limit:
                        break

    return SuggestResponse(suggestions=suggestions[:limit])