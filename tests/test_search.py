import uuid
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.search import hybrid_search, search_suggest, SearchTenantRequiredError
from app.schemas.search import SearchRequest, SearchResponse, SearchResult, SuggestResponse


class TestSearchTenantGuard:
    """Tests for tenant context validation in search."""

    @pytest.mark.asyncio
    async def test_hybrid_search_raises_without_tenant(self):
        """Search should raise SearchTenantRequiredError when tenant_id is None."""
        mock_db = AsyncMock(spec=AsyncSession)
        
        with pytest.raises(SearchTenantRequiredError, match="Search requires tenant context"):
            await hybrid_search(
                db=mock_db,
                tenant_id=None,
                query="test query",
                top_k=10,
                hybrid_weight=0.5,
            )
        
        mock_db.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_suggest_raises_without_tenant(self):
        """Suggest should raise SearchTenantRequiredError when tenant_id is None."""
        mock_db = AsyncMock(spec=AsyncSession)
        
        with pytest.raises(SearchTenantRequiredError, match="Search requires tenant context"):
            await search_suggest(
                db=mock_db,
                tenant_id=None,
                q="test",
                limit=5,
            )
        
        mock_db.execute.assert_not_called()


class TestSearchDeterminism:
    """Tests for deterministic ranking."""

    @pytest.mark.asyncio
    async def test_hybrid_search_deterministic_order(self):
        """Same query should return results in identical order across multiple calls."""
        mock_db = AsyncMock(spec=AsyncSession)
        tenant_id = uuid.uuid4()
        
        mock_row = MagicMock()
        mock_row.mappings.return_value.all.return_value = [
            {"id": uuid.uuid4(), "document_id": uuid.uuid4(), "chunk_index": 0, 
             "content": "chunk 1", "original_filename": "doc1.txt", "bm25_score": 0.9},
            {"id": uuid.uuid4(), "document_id": uuid.uuid4(), "chunk_index": 1, 
             "content": "chunk 2", "original_filename": "doc1.txt", "bm25_score": 0.8},
        ]
        mock_db.execute.return_value = mock_row
        
        with patch("app.services.search._embed_text", return_value=[0.1] * 384):
            results = []
            for _ in range(5):
                response = await hybrid_search(
                    db=mock_db,
                    tenant_id=tenant_id,
                    query="test query",
                    top_k=10,
                    hybrid_weight=0.5,
                )
                results.append([r.chunk_index for r in response.results])
            
            for i in range(1, len(results)):
                assert results[i] == results[0], f"Run {i} order differs from run 0"


class TestSearchIntegration:
    """Integration tests for search endpoints."""

    @pytest.mark.asyncio
    async def test_search_endpoint_requires_tenant_context(self, async_client, token_a_admin):
        """Search endpoint should work with valid tenant token."""
        response = await async_client.post(
            "/search",
            json={"query": "test", "top_k": 10, "hybrid_weight": 0.5},
            headers={"Authorization": f"Bearer {token_a_admin}"},
        )
        assert response.status_code in (200, 404)  # 404 if no chunks indexed

    @pytest.mark.asyncio
    async def test_suggest_endpoint_requires_tenant_context(self, async_client, token_a_admin):
        """Suggest endpoint should work with valid tenant token."""
        response = await async_client.get(
            "/search/suggest?q=test&limit=5",
            headers={"Authorization": f"Bearer {token_a_admin}"},
        )
        assert response.status_code in (200, 404)