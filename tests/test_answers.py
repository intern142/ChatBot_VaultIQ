"""VQ-207: Answer engine tests — extraction, routing, no-LLM guard, isolation.

The engine is retrieval-only: answers are sentences lifted verbatim from
the tenant's own chunks. These tests prove routing (answer / partial /
no_answer), the "never a random excerpt" guarantee (HeXta bug 2),
tenant-content-only follow-ups, spectral corpus-gated spellcheck with
confirmation, and that no LLM module or field can be imported/used.
"""

import importlib.util
import pathlib
import re
import uuid
from typing import List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.schemas.answer import AnswerResponse, SpellCorrection
from app.schemas.search import SearchResponse, SearchResult
from app.services.answers import (
    ANSWER_CONFIDENCE,
    NO_ANSWER_RELEVANCE_FLOOR,
    PARTIAL_CONFIDENCE,
    _correct_query,
    _extract_answer_phrase,
    _recalibrate_confidence,
    _route_by_confidence,
    _suggest_followups,
    answer_question,
)
from app.services.search import SearchTenantRequiredError

PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent
APP_DIR = PROJECT_ROOT / "app"

# The optional LLM layer that VQ-207 removes: cloud/API SDKs.
BANNED_SDK_PREFIXES = (
    "openai", "anthropic", "langchain", "langgraph", "llama_index",
    "llamaindex", "litellm", "groq", "cohere", "mistralai", "together",
    "replicate", "google.generativeai", "vertexai", "amazon.bedrock",
    "azure.ai", "transformers", "torch", "tensorflow",
)

# HeXta's LLM synthesis surface explicitly banned from responses/code.
BANNED_LLM_TOKENS = (
    "llm_model", "synthesized", "grounding_validator", "complexity_router",
    "circuit_breaker", "cost_analytics", "feature_flag",
)


def _app_source() -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in APP_DIR.rglob("*.py"))


# ---- No-LLM guard (AC 2: the LLM layer is removed entirely) -----------

def test_app_source_never_imports_llm_sdks():
    source = _app_source()
    pattern = re.compile(
        r"^\s*(from|import)\s+(" + "|".join(re.escape(p) for p in BANNED_SDK_PREFIXES) + r")(\.|\s)",
        re.MULTILINE,
    )
    matches = pattern.findall(source)
    assert not matches, f"LLM SDK imports found in app: {matches}"


def test_app_source_has_no_llm_synthesis_fields():
    source = _app_source()
    for token in BANNED_LLM_TOKENS:
        assert token not in source, f"banned LLM token '{token}' still present in app/"


def test_answer_response_has_no_llm_fields():
    from app.schemas.answer import AnswerResponse
    assert "synthesized" not in AnswerResponse.model_fields
    assert "llm_model" not in AnswerResponse.model_fields


def test_llm_sdk_packages_not_importable_by_app():
    """No LLM SDK should be importable from the app environment.

    The repo strips the AI-writing layer entirely; a transitive import of
    any of these would break the "no generated text" rule.
    ("google"/"amazon"/"azure" are namespace parents of unrelated deps and
    are checked as exact import paths by the source scan instead.)
    """
    single_parts = (p for p in BANNED_SDK_PREFIXES if "." not in p)
    for mod in single_parts:
        spec = importlib.util.find_spec(mod)
        assert spec is None, f"LLM package '{mod}' is importable in the app environment"


# ---- Routing helpers (kept from HeXta: answer / partial / no_answer) --

def test_route_by_confidence():
    assert _route_by_confidence(ANSWER_CONFIDENCE) == "answer"
    assert _route_by_confidence(95.0) == "answer"
    assert _route_by_confidence(PARTIAL_CONFIDENCE) == "partial"
    assert _route_by_confidence(74.5) == "partial"
    assert _route_by_confidence(49.9) == "no_answer"


def test_recalibrate_confidence_never_increases():
    assert _recalibrate_confidence(100.0, 0.80) == 100.0
    assert _recalibrate_confidence(60.0, 0.70) == 60.0
    assert _recalibrate_confidence(60.0, 1.00) == 60.0
    assert _recalibrate_confidence(60.0, 0.50) < 60.0
    assert _recalibrate_confidence(60.0, 0.00) < 60.0
    assert _recalibrate_confidence(100.0, 0.0) < 100.0


# ---- Extractive answer-phrase selection --------------------------------

CHUNK = (
    "The annual leave policy entitles employees to twenty working days "
    "per year. Annual leave must be approved by the manager two weeks in advance."
)


def test_phrase_is_verbatim_from_chunk():
    phrase = _extract_answer_phrase(CHUNK, "what is the annual leave policy")
    assert phrase in CHUNK, "answer must be a verbatim sentence, never a paraphrase"
    assert phrase.endswith(".")


def test_phrase_skips_heading_footer_and_question():
    chunk = "Annual Leave\\nThe sky is blue.\\nSource: Internal Policy 2025"
    chunk = chunk.replace("\\n", "\n")
    phrase = _extract_answer_phrase(chunk, "what colour is the sky")
    assert phrase == "The sky is blue."


def test_phrase_skips_trailing_question():
    chunk = "The policy is final. What is the review process?"
    phrase = _extract_answer_phrase(chunk, "tell me about the policy")
    assert phrase == "The policy is final."


def test_phrase_short_statement_fallback():
    assert _extract_answer_phrase("Yes.", "can we approve expenses?") == "Yes."


def test_phrase_empty_when_no_sentence():
    assert _extract_answer_phrase("", "anything") == ""
    assert _extract_answer_phrase(None, "anything") == ""


def test_phrase_truncates_runons():
    long = "The " + " ".join(["overview"] * 80) + " sentence continues beyond the limit."
    phrase = _extract_answer_phrase(long, "overview")
    assert len(phrase) <= 300
    assert phrase.endswith("…")


def test_phrase_prefers_sentence_with_number_when_question_wants_number():
    chunk = "The budget for 2025 was approved. The budget for next year is uncertain."
    phrase = _extract_answer_phrase(chunk, "what was the approved budget for 2025")
    assert "2025" in phrase


def test_phrase_merges_abbreviation_fragment():
    chunk = "Per policy Jordan A. Rivera may approve expenses. He reviews monthly."
    phrase = _extract_answer_phrase(chunk, "who may approve expenses per policy")
    assert "Jordan A. Rivera may approve expenses" in phrase


def test_phrase_deterministic():
    a = _extract_answer_phrase(CHUNK, "annual leave")
    b = _extract_answer_phrase(CHUNK, "annual leave")
    assert a == b


# ---- Corpus-gated spellcheck confirmation ------------------------------

VOCAB = ["address", "advance", "annual", "approval", "approve", "expenses",
         "leave", "manager", "policy", "staff", "travel", "working"]


def test_spellcheck_corrects_typo_against_corpus():
    corrected, fixes = _correct_query("what is the anual leave policy", VOCAB)
    assert fixes == [SpellCorrection(original_term="anual", corrected_term="annual")]
    assert "anual" not in corrected
    assert "annual" in corrected


def test_spellcheck_never_corrects_numbers():
    corrected, fixes = _correct_query("maximum allowance is 5000", VOCAB)
    assert fixes == []
    assert "5000" in corrected


def test_spellcheck_never_rewrites_a_real_corpus_term():
    # HeXta false-positive class: a genuine domain term must not be turned
    # into a dictionary twin simply because it looks close to one.
    vocab = ["respa", "repa", "respaw", "buyback", "salary"]
    corrected, fixes = _correct_query("what is the respa policy", vocab)
    assert fixes == []
    assert "respa" in corrected


def test_spellcheck_leaves_known_words_alone():
    corrected, fixes = _correct_query("annual leave policy", VOCAB)
    assert fixes == []
    assert corrected == "annual leave policy"


# ---- Follow-ups come only from the tenant's own content ----------------

def _result(content: str, score: float = 0.0164) -> SearchResult:
    return SearchResult(
        document_id=uuid.uuid4(),
        chunk_index=0,
        content=content,
        score=round(score, 4),
        original_filename="doc.txt",
    )


def test_followups_only_from_content_and_exclude_question():
    results = [
        _result("Employees accrue twenty working days of annual leave each year."),
        _result("Leave approval is handled by the manager in advance."),
    ]
    followups = _suggest_followups("what is the annual leave policy", results)
    assert followups
    for f in followups:
        assert f.endswith("?")
    for t in _followup_terms(followups):
        assert t != "annual" and t != "leave" and t != "policy"
        assert any(t in r.content for r in results), f"follow-up topic '{t}' not in tenant content"


def _followup_terms(followups: List[str]) -> List[str]:
    return [re.sub(r"[^a-z0-9' ]", "", f).split().pop() for f in followups]


def test_followups_empty_without_results():
    assert _suggest_followups("anything", []) == []


# ---- answer_question service (hybrid_search mocked) --------------------

def _search_response(contents: List[tuple], query="q") -> SearchResponse:
    return SearchResponse(
        results=[_result(c, s) for c, s in contents],
        query=query,
        total_results=len(contents),
    )


class TestAnswerService:
    @staticmethod
    def _mock_db(vocab: list = None) -> AsyncMock:
        mock_db = AsyncMock(spec=AsyncSession)
        result = MagicMock()
        result.mappings.return_value = [{"word": w} for w in (vocab or [])]
        mock_db.execute.return_value = result
        return mock_db

    @pytest.mark.asyncio
    async def test_answer_raises_without_tenant_before_db(self):
        mock_db = AsyncMock(spec=AsyncSession)
        with pytest.raises(SearchTenantRequiredError, match="requires tenant context"):
            await answer_question(db=mock_db, tenant_id=None, question="anything")
        mock_db.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_in_document_question_returns_answer(self):
        mock_db = self._mock_db()
        content = CHUNK
        response = _search_response([(content, 1 / 61)])
        with patch("app.services.answers.hybrid_search", new=AsyncMock(return_value=response)):
            result = await answer_question(
                db=mock_db, tenant_id=uuid.uuid4(),
                question="how many days of annual leave do staff get per year",
            )
        assert result.routing == "answer"
        assert result.confidence >= ANSWER_CONFIDENCE
        assert result.answer_phrase in CHUNK
        assert result.sources and result.sources[0].excerpt == content
        assert result.source_document_id is not None
        assert result.followups

    @pytest.mark.asyncio
    async def test_out_of_document_no_answer_never_random_excerpt(self):
        """HeXta bug 2: even when a chunk phrase is extractable, an
        off-topic question must return a clean no_answer, an empty phrase
        and no sources — never a random excerpt."""
        mock_db = self._mock_db()
        content = "Six sigma belts are earned after completing the green belt exam."
        response = _search_response([(content, 1 / 61)])
        with patch("app.services.answers.hybrid_search", new=AsyncMock(return_value=response)):
            result = await answer_question(
                db=mock_db, tenant_id=uuid.uuid4(),
                question="how many holiday days do staff get each year",
            )
        assert result.routing == "no_answer"
        assert result.answer_phrase == ""
        assert result.sources == []
        assert result.followups == []

    @pytest.mark.asyncio
    async def test_no_results_no_answer(self):
        mock_db = self._mock_db()
        response = _search_response([])
        with patch("app.services.answers.hybrid_search", new=AsyncMock(return_value=response)):
            result = await answer_question(
                db=mock_db, tenant_id=uuid.uuid4(), question="anything",
            )
        assert result.routing == "no_answer"
        assert result.confidence == 0.0

    @pytest.mark.asyncio
    async def test_partial_routing(self):
        mock_db = self._mock_db()
        content = "The annual leave policy covers annual leave accrual for all staff."
        # relevance = 3/4 query terms present; base confidence sits in the
        # partial band so routing must be "partial".
        response = _search_response([(content, 0.6 / 61)])
        with patch("app.services.answers.hybrid_search", new=AsyncMock(return_value=response)):
            result = await answer_question(
                db=mock_db, tenant_id=uuid.uuid4(),
                question="what are the annual leave accrual rates",
            )
        assert result.routing == "partial"
        assert PARTIAL_CONFIDENCE <= result.confidence < ANSWER_CONFIDENCE
        assert result.answer_phrase in content

    @pytest.mark.asyncio
    async def test_spellcheck_applied_and_echoed(self):
        mock_db = self._mock_db()
        mocked_search = AsyncMock(return_value=_search_response([(CHUNK, 1 / 61)]))
        with patch("app.services.answers.hybrid_search", new=mocked_search), \
             patch("app.services.answers._tenant_vocabulary",
                   new=AsyncMock(return_value=VOCAB + ["annual", "leave", "days", "working"])):
            result = await answer_question(
                db=mock_db, tenant_id=uuid.uuid4(),
                question="how many days of anual leave per year",
            )
        assert result.spellcheck.applied is True
        assert result.spellcheck.corrected == "how many days of annual leave per year"
        assert result.spellcheck.corrections[0].corrected_term == "annual"
        assert result.spellcheck.original == "how many days of anual leave per year"
        mocked_search.assert_awaited()
        call_kwargs = mocked_search.call_args.kwargs
        assert call_kwargs["query"] == "how many days of annual leave per year"

    @pytest.mark.asyncio
    async def test_deterministic_response(self):
        mock_db = self._mock_db()
        response = _search_response([(CHUNK, 1 / 61)])
        with patch("app.services.answers.hybrid_search", new=AsyncMock(return_value=response)):
            a = await answer_question(
                db=mock_db, tenant_id=uuid.uuid4(),
                question="how many days of annual leave per year",
            )
            b = await answer_question(
                db=mock_db, tenant_id=uuid.uuid4(),
                question="how many days of annual leave per year",
            )
        assert a.model_dump() == b.model_dump()


# ---- Endpoint wiring ----------------------------------------------------

class TestAnswerEndpoint:
    @pytest.mark.asyncio
    async def test_requires_bearer_token(self, async_client):
        # HTTPBearer returns 403 when no Authorization header is present.
        resp = await async_client.post("/answers", json={"question": "anything"})
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_invalid_token_rejected(self, async_client):
        resp = await async_client.post(
            "/answers",
            json={"question": "anything"},
            headers={"Authorization": "Bearer not-a-real-token"},
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_super_admin_denied(self, async_client, super_admin_token):
        resp = await async_client.post(
            "/answers",
            json={"question": "anything"},
            headers={"Authorization": f"Bearer {super_admin_token}"},
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_tenant_user_can_ask_and_no_results_is_clean(
        self, async_client, token_a_admin, tenant_a
    ):
        response = _search_response([])
        with patch("app.services.answers.hybrid_search", new=AsyncMock(return_value=response)):
            resp = await async_client.post(
                "/answers",
                json={"question": "what is the policy"},
                headers={"Authorization": f"Bearer {token_a_admin}"},
            )
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["routing"] == "no_answer"
        assert payload["answer_phrase"] == ""
        assert payload["sources"] == []
        assert payload["question"] == "what is the policy"


# ---- Seeded integration: real chunks, real route -----------------------

@pytest.mark.asyncio
async def test_seeded_chunks_in_document_and_out_of_document(
    async_client, token_a_admin, tenant_a, db_engine
):
    """End-to-end through the real hybrid path with an actual chunk.

    Patching only the query embedding keeps the test offline and fast
    while still exercising the true SQL, ranking and extraction pipeline.
    """
    tenant_id = tenant_a["id"]
    admin_uid = tenant_a["client_admin"]["id"]
    partition = "document_chunks_p_" + str(tenant_id).replace("-", "")

    embedding = "[" + ",".join(["0.1"] * 384) + "]"
    content = (
        "The annual leave policy entitles employees to twenty working days "
        "per year. Annual leave must be approved by the manager two weeks in advance."
    )

    async with db_engine.begin() as conn:
        await conn.execute(text(f"""
            CREATE TABLE IF NOT EXISTS {partition}
            PARTITION OF document_chunks FOR VALUES IN ('{tenant_id}')
        """))
        doc = await conn.execute(text("""
            INSERT INTO documents (id, tenant_id, original_filename, stored_filename,
                                   mime_type, size_bytes, uploaded_by)
            VALUES (gen_random_uuid(), :tid, 'annual-leave.txt', 'annual-leave.txt', 'text/plain', 128, :uid)
            RETURNING id
        """), {"tid": tenant_id, "uid": admin_uid})
        doc_id = doc.scalar()
        await conn.execute(text("""
            INSERT INTO document_chunks (tenant_id, document_id, chunk_index, content, embedding)
            VALUES (:tid, :doc_id, 0, :content, :embedding)
        """), {
            "tid": tenant_id, "doc_id": doc_id,
            "content": content, "embedding": embedding,
        })

    headers = {"Authorization": f"Bearer {token_a_admin}"}

    with patch("app.services.search._embed_text",
               side_effect=lambda _t: [0.1] * 384):
        # In-document question -> verbatim answer sentence.
        resp = await async_client.post(
            "/answers",
            json={"question": "what is the annual leave policy", "top_k": 5},
            headers=headers,
        )
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["routing"] in ("answer", "partial")
        assert payload["answer_phrase"] in content
        assert payload["sources"], "in-document answer must carry sources"
        assert payload["source_document_id"] == str(doc_id)

        # Out-of-document question -> clean no_answer, never a random excerpt.
        resp = await async_client.post(
            "/answers",
            json={"question": "what is the pension contribution rate", "top_k": 5},
            headers=headers,
        )
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["routing"] == "no_answer"
        assert payload["answer_phrase"] == ""
        assert payload["sources"] == []

        # Real vocabulary drives the spellcheck confirmation end-to-end.
        resp = await async_client.post(
            "/answers",
            json={"question": "what is the anual leave policy", "top_k": 5},
            headers=headers,
        )
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["spellcheck"]["applied"] is True
        assert payload["spellcheck"]["corrected"] == "what is the annual leave policy"
        assert payload["answer_phrase"] in content