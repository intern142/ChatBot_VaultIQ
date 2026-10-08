import uuid
from typing import List
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document
from app.models.search import DocumentChunk
from app.schemas.search import SearchRequest, SearchResponse, SearchResult, SuggestRequest, SuggestResponse


class SearchTenantRequiredError(Exception):
    """Raised when search is attempted without a valid tenant context."""
    pass


async def hybrid_search(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    query: str,
    top_k: int,
    hybrid_weight: float,
) -> SearchResponse:
    """
    Hybrid search combining keyword (BM25) and vector similarity.
    Uses Reciprocal Rank Fusion (RRF) to combine scores.
    Deterministic ordering: combined_score DESC, chunk_id ASC.
    """
    if not tenant_id:
        raise SearchTenantRequiredError("Search requires tenant context")

    query = query.strip()
    query_embedding = _embed_text(query)
    query_embedding_str = '[' + ','.join(str(x) for x in query_embedding) + ']'

    k = 60

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
        {"tenant_id": tenant_id, "query": query, "limit": top_k * 2}
    )
    keyword_rows = keyword_result.mappings().all()

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
        {"tenant_id": tenant_id, "embedding": query_embedding_str, "limit": top_k * 2}
    )
    vector_rows = vector_result.mappings().all()

    scores = {}

    for rank, row in enumerate(keyword_rows, 1):
        chunk_id = row['id']
        rrf_score = 1.0 / (k + rank)
        scores[chunk_id] = (rrf_score * (1 - hybrid_weight), row)

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

    sorted_results = sorted(
        scores.items(),
        key=lambda x: (-x[1][0], str(x[0]))
    )[:top_k]

    results = [
        SearchResult(
            document_id=row['document_id'],
            chunk_index=row['chunk_index'],
            content=row['content'][:500],
            score=round(score, 4),
            original_filename=row['original_filename'],
        )
        for chunk_id, (score, row) in sorted_results
    ]

    return SearchResponse(
        results=results,
        query=query,
        total_results=len(results),
    )


async def search_suggest(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    q: str,
    limit: int,
) -> SuggestResponse:
    """
    Autocomplete suggestions based on indexed content.
    Uses tsvector prefix matching.
    """
    if not tenant_id:
        raise SearchTenantRequiredError("Search requires tenant context")

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
        {"tenant_id": tenant_id, "query": q, "limit": limit}
    )
    rows = result.mappings().all()

    suggestions = []
    for row in rows:
        if row['highlight']:
            words = row['highlight'].split()
            for w in words:
                clean = w.strip('.,!?()[]{}"\'')
                if len(clean) > 2 and clean.lower() not in [s.lower() for s in suggestions]:
                    suggestions.append(clean)
                    if len(suggestions) >= limit:
                        break

    return SuggestResponse(suggestions=suggestions[:limit])


def _embed_text(text: str) -> List[float]:
    """Generate embedding for a single text using FastEmbed."""
    from app.services.embeddings import embed_text
    return embed_text(text)