# VQ-207 Self-Review: Answer Engine is Retrieval-Only (No LLM Layer)

## Acceptance Criteria Walkthrough

### AC1: Extractive answer selection, confidence score and answer / partial / no_answer routing kept from HeXta
**Status: ✅ CONFIRMED**

**Implementation:** `app/services/answers.py` keeps HeXta's three-band routing and its extractive selection:

| HeXta behaviour (referenced, never imported) | VQ-207 equivalent |
|---|---|
| `ANSWER_CONFIDENCE=90`, `PARTIAL_CONFIDENCE=50` | `ANSWER_CONFIDENCE=90.0`, `PARTIAL_CONFIDENCE=50.0` in `app/services/answers.py` |
| `no_answer` below the low band | `_route_by_confidence()` → `no_answer` |
| Extractive sentence selection | `_extract_answer_phrase()` — verbatim sentences only |
| Confidence from ranking strength | `_base_confidence()` = `min(top_rrf_score * (K+1) * 100, 100)` with `K=60` (matches `app/services/search.py`) |
| Tune confidence against evidence relevance | `_recalibrate_confidence()` — scales **down only**, never up |

**Evidence:** `tests/test_answers.py` — `test_route_by_confidence`, `test_recalibrate_confidence_never_increases`,
`TestAnswerService::test_in_document_question_returns_answer` (routing `answer`),
`test_partial_routing`, `test_out_of_document_no_answer_never_random_excerpt`, phrase-extraction suite.

---

### AC2: Everything related to LLM synthesis is removed from the codebase and the responses
**Status: ✅ CONFIRMED**

The answer response has **no generative fields** and the app makes **no LLM import and no reference to the old
synthesis layer**:

- `AnswerResponse` carries only question, `answer_phrase` (extracted text), routing, confidence, extractive
  sources, follow-ups and spellcheck confirmation. **No `synthesized`, no `llm_model`.**
- No LLM client, feature flag, grounding validator, complexity router, circuit breaker or cost analytics exists:
  `BANNED_SDK_PREFIXES` and `BANNED_LLM_TOKENS` source scans in `tests/test_answers.py` return zero matches
  across `app/`.
- HeXta's `synthesized`/`llm_model` were never present in VaultIQ (separate codebase — `G:\Hexta-v1` is
  reference only); nothing was re-introduced.

**Evidence:**
- `test_app_source_never_imports_llm_sdks` — no `openai`/`anthropic`/`langchain`/`litellm`/`transformers`/etc import in `app/`.
- `test_app_source_has_no_llm_synthesis_fields` — banned tokens absent from `app/`.
- `test_answer_response_has_no_llm_fields` — schema field guard (`'synthesized' not in AnswerResponse.model_fields`).
- `test_llm_sdk_packages_not_importable_by_app` — env `find_spec` guard (single-part SDKs).
- Grep evidence from the commit: `rg "synthesized|llm_model" app/` returns nothing in code.

---

### AC3: Question whose answer is not in the tenant's documents → clean 'not found', never a random excerpt (HeXta bug 2)
**Status: ✅ CONFIRMED**

**Implementation:** `answer_question()` computes query↔evidence relevance over the top excerpt and any
extractable phrase. If `relevance < NO_ANSWER_RELEVANCE_FLOOR` (0.35) it returns `routing="no_answer"` with:
- empty `answer_phrase`
- empty `sources`
- empty `followups`

**This fires even when a phrase is extractable** — exactly HeXta bug 2's failure mode, so it cannot come back.

**Evidence:**
- `TestAnswerService::test_out_of_document_no_answer_never_random_excerpt` — a chunk whose sentence *is*
  extractable returns fully empty `no_answer` because the question is off-topic.
- Seeded end-to-end `test_seeded_chunks_in_document_and_out_of_document` — real chunk in the DB:
  in-document question → `answer` with a verbatim phrase; out-of-document question → `no_answer` with empty
  phrase + empty sources, through the **real search SQL**.

---

### AC4: Follow-up suggestions come only from the tenant's own content
**Status: ✅ CONFIRMED**

**Implementation:** `_suggest_followups()` counts content terms **only from the retrieved chunk contents**
(`results[*].content`), excludes the words in the user's question and the static starters/stopwords, and picks
the top ≤3. The subject of each suggestion is always a term physically present in a tenant chunk; the
surrounding skeleton is a fixed template (`"What is {term}?"`, etc.) — nothing generic is invented.

**Evidence:** `test_followups_only_from_content_and_exclude_question` asserts every follow-up topic appears in
tenant content and never reuses question terms; `test_followups_empty_without_results`.

---

### AC5: Spellcheck confirmation works and the known false positives from the HeXta report are fixed
**Status: ✅ CONFIRMED**

**Implementation:** `_correct_query()` is gated **entirely by the tenant's own corpus vocabulary**
(`_tenant_vocabulary` from `document_chunks`, most-frequent-first, capped at 20,000). A token is corrected
only when ALL hold (each mapped to a HeXta false-positive class):

1. purely alphabetic and ≥4 chars → **numbers/amounts are never touched**;
2. NOT already a vocabulary word → **a real domain term is never rewritten into a dictionary twin**
   (HeXta false-positive class "respa" → "repay" cannot happen);
3. a fuzzy match at ratio ≥ 0.80 exists against a corpus word (`difflib`).

Confirmation is echoed back in `spellcheck.{applied, original, corrected, corrections}` so the UI can show
what was fixed — and corrections are capped at 3.

**Evidence:** `test_spellcheck_corrects_typo_against_corpus`, `test_spellcheck_never_corrects_numbers`,
`test_spellcheck_never_rewrites_a_real_corpus_term` (the "respa" class), `test_spellcheck_leaves_known_words_alone`,
`TestAnswerService::test_spellcheck_applied_and_echoed`, and the seeded end-to-end real-vocab confirmation.

---

## Must-Be-Proven Status

| Requirement | Status |
|---|---|
| Automated test that no LLM-related module can be imported + grep evidence fields are gone | ✅ Done (Gate 3): 4 guard tests, all green |
| Benchmark before and after with no regression | ⏳ Pending (Gate 6): baseline in `benchmark_results.json` (VQ-205); run `evaluation/run_benchmark.py` against live container and compare |
| Live container evidence: 5 in-document + 5 out-of-document questions with routing | ⏳ Pending (Gate 6) |

## Common Mistakes Checklist (from `.github/CHECKLIST.md`)

| Check | Status | Notes |
|---|---|---|
| No hardcoded secrets | ✅ | None in new files |
| No outbound network calls at runtime | ✅ | FastEmbed loads from local cache; no new I/O |
| No LLM / no generated text | ✅ | Extractive only; source + import guards in tests |
| Tenant isolation enforced | ✅ | `SearchTenantRequiredError` before any DB call + tenant-scoped vocabulary query + tenant-scoped hybrid search |
| No cross-tenant data in responses | ✅ | `TestAnswerEndpoints` body-leak checks in isolation suite |
| Super Admin denied on content endpoints | ✅ | `require_roles_with_tenant("client_admin","employee")`; 403 tested |
| Error messages don't leak info | ✅ | Generic messages only |
| Input validation on user-facing endpoint | ✅ | `AnswerRequest` Pydantic `Field` constraints (question 1-500, top_k 1-50, hybrid_weight 0-1) |
| SQL injection not possible | ✅ | Parameterized SQLAlchemy `text()` queries only |
| Request/response schemas validated | ✅ | `response_model=AnswerResponse` on the route |
| Response format consistent with /search | ✅ | Same success/error shapes, same auth/tenant plumbing |
| Unused imports / dead code | ✅ | None introduced |
| Tests deterministic | ✅ | RRF ties broken by chunk id; phrase `max()` is stable; 5× determinism test |
| Commits carry story ID | ✅ | `f20e561` (Gate 2), `5ee561d` (AGENTS.md) |

## Test Coverage Summary (Gate 3)

| Test File | Tests | Coverage |
|---|---|---|
| `tests/test_answers.py` | 33 | No-LLM guards (4), routing (3), recalibration (1), phrase extraction (8), spellcheck (4), follow-ups (3), service (7), endpoint (4), seeded end-to-end (1) |
| `tests/test_isolation_suite.py::TestAnswerEndpoints` | 5 | Cross-tenant body-leak ×4 role/token pairs, Super Admin 403 |
| `tests/isolation_manifest.py` | (+1) | `("POST", "/answers")` registered → coverage guard green |

**Full suite: 188 passed** (test_answers 33 + permissions 21 + isolation 49 + rest 105).

## Files Modified/Created (Gate 2)

| File | Type |
|---|---|
| `app/schemas/answer.py` | New |
| `app/services/answers.py` | New |
| `app/routes/answers.py` | New |
| `app/main.py` | Modified (+router) |
| `app/auth/permissions.py` | Modified (+3 ROLE_MATRIX entries; also fixes VQ-205 router-walk carryover) |
| `tests/test_answers.py` | New |
| `tests/isolation_manifest.py` | Modified |
| `tests/test_isolation_suite.py` | Modified (+TestAnswerEndpoints, +prefix) |
| `AGENTS.md` | Modified (Gate 1-3 record) |

## Ready for Gate 5 (Code Review)

- [x] Approach note approved (Gate 1)
- [x] Implementation complete (Gate 2)
- [x] Tests written and green (Gate 3)
- [x] Self-review: all 5 ACs walked and confirmed (Gate 4)
- [ ] Code review (Gate 5)
- [ ] Live container verify (Gate 6) — 5 in-doc + 5 out-of-doc questions, benchmark no-regression
- [ ] Demo & sign-off (Gate 7)

---

**Self-Review Completed:** All 5 acceptance criteria confirmed. "Must Be Proven" benchmark + live-container
evidence are scheduled for Gate 6.

**PR note:** this branch stacks on VQ-205 (search), which has no open PR — the vq-207 → main diff therefore
also carries the VQ-205 search stack (migration 010, /search endpoints). If the reviewer needs VQ-205
reviewed first, VQ-207 can be re-targeted after VQ-205 merges.