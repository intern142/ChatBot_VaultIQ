# VQ-305 Approach Note: Answer Feedback Capture

## Objective
Employees can tell their Client Admin which answers were wrong or unhelpful via thumbs up/down + optional comment.

## Acceptance Criteria
1. Thumbs up or down plus optional short comment on any answer; one vote per user per answer, changeable
2. Stored with tenant, user, answer, and which documents were used
3. Available to Client Admin dashboard (VQ-302) and, for not-found answers with negative feedback, to knowledge gaps

## Current State
- Answers are returned from `/search` endpoint (VQ-204) with document references
- No answer ID concept yet — search returns chunks directly
- Need to introduce `Answer` model to track what was shown to user

## Design Decisions

### 1. Answer Model
```sql
CREATE TABLE answers (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    question text NOT NULL,
    answer_text text,  -- NULL if not found
    confidence float,  -- 0-1, NULL if not found
    source_document_ids uuid[] NOT NULL DEFAULT '{}',
    source_chunk_ids uuid[] NOT NULL DEFAULT '{}',
    created_at timestamptz NOT NULL DEFAULT now()
);
```
- One row per question asked
- Links to source documents/chunks for traceability
- `answer_text` NULL = "not found"
- `confidence` NULL = "not found"

### 2. Feedback Model
```sql
CREATE TABLE answer_feedback (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    answer_id uuid NOT NULL REFERENCES answers(id) ON DELETE CASCADE,
    vote smallint NOT NULL CHECK (vote IN (1, -1)),  -- 1 = up, -1 = down
    comment text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (answer_id, user_id)  -- one vote per user per answer
);
```
- Unique constraint enforces one vote per user per answer
- `vote`: 1 (thumbs up) or -1 (thumbs down)
- `comment`: optional, max 500 chars
- `updated_at` tracks changes (vote changeable)

### 3. Search Integration
- Modify `POST /search` to:
  1. Execute search as before
  2. Create `Answer` record with question, results, source docs
  3. Return `answer_id` in response
- New endpoint: `POST /answers/{answer_id}/feedback`
- New endpoint: `GET /answers/{answer_id}/feedback` (for Client Admin)

### 4. Endpoints
| Endpoint | Auth | Purpose |
|----------|------|---------|
| `POST /answers/{answer_id}/feedback` | employee, client_admin | Submit/update feedback |
| `GET /answers/{answer_id}/feedback` | client_admin | View feedback for answer |
| `GET /answers/feedback` | client_admin | List all feedback (paged, filtered) |

### 5. Knowledge Gaps Integration (VQ-302)
- Negative feedback on `answer_text IS NULL` → feeds "not found" knowledge gaps
- Low confidence + negative feedback → feeds "low confidence" knowledge gaps
- Aggregated by question similarity (future: pgvector on questions)

### 6. RLS & Security
- Both tables: FORCE RLS on `tenant_id = current_setting('app.current_tenant')`
- `vaultiq_app`: CRUD on both
- `vaultiq_super_admin`: SELECT only (for platform analytics)
- Employee: can only create/update own feedback
- Client Admin: can view all feedback in their tenant

## Files to Create/Modify

### New Files
| File | Purpose |
|------|---------|
| `app/models/feedback.py` | Answer, AnswerFeedback models |
| `app/schemas/feedback.py` | Request/response schemas |
| `app/routes/feedback.py` | Feedback endpoints |
| `alembic/versions/011_feedback.py` | Migration |

### Modified Files
| File | Change |
|------|--------|
| `app/models/__init__.py` | Export Answer, AnswerFeedback |
| `app/routes/search.py` | Create Answer record, return answer_id |
| `app/main.py` | Register feedback router |
| `app/auth/permissions.py` | Add feedback endpoints to ROLE_MATRIX |

## Tests to Write
1. **Unit**: Vote validation (only 1/-1), comment length, unique constraint
2. **Integration**: Submit feedback → update feedback → retrieve feedback
3. **Integration**: Search returns answer_id, feedback linked correctly
4. **Authorization**: Employee can only vote on own answers; Client Admin sees all
5. **Isolation**: Tenant A feedback not visible to Tenant B (add to isolation suite)

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Answer table grows large | Partition by tenant_id (same pattern as document_chunks) |
| Feedback on old answers | Answer.id is immutable; feedback always links to specific answer |
| Concurrent vote updates | Unique constraint + UPDATE handles race condition |

## Gate 3 Acceptance
- All new tests pass
- Full existing suite (137) stays green
- Isolation suite covers `/answers/*` endpoints

## Gate 6 Evidence
- Create answer via search, submit feedback as employee
- Verify Client Admin sees feedback in list
- Verify negative feedback on not-found answer tracked
- Cross-tenant isolation verified

---

## Questions for Reviewer

1. **Answer model**: Store full answer text + source docs, or just references? Full text for audit trail.
2. **Confidence score**: How to compute? For now: 1.0 if exact match, 0.5 if partial, NULL if not found. Defer ML-based confidence.
3. **Question deduplication**: Same question asked twice → two Answer rows (different contexts). OK?
4. **Feedback on search vs chat**: Currently only search exists. Future chat will reuse Answer model.