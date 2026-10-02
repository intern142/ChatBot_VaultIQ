# VQ-305 Self-Review: Answer Feedback Capture

## Acceptance Criteria Verification

### AC1: Thumbs up/down + optional comment; one vote per user per answer, changeable
✅ **Verified**: 
- `FeedbackCreate` schema validates vote ∈ {1, -1}, comment ≤500 chars
- `AnswerFeedback` model has unique constraint on (answer_id, user_id)
- PATCH endpoint allows updating vote and/or comment
- Tests: `test_create_feedback_success`, `test_create_feedback_negative_vote`, `test_update_feedback`, `test_create_feedback_duplicate_fails`

### AC2: Stored with tenant, user, answer, and which documents were used
✅ **Verified**:
- `AnswerFeedback` model has tenant_id, user_id, answer_id FKs
- `Answer` model has source_document_ids, source_chunk_ids arrays
- RLS enforced on both tables via `tenant_id = current_setting('app.current_tenant')`
- Tests: `test_cross_tenant_feedback_isolation` proves tenant isolation

### AC3: Available to Client Admin dashboard (VQ-302) and knowledge gaps
✅ **Ready**:
- `GET /answers/feedback` with pagination/filtering for Client Admin
- Negative feedback on `answer_text IS NULL` (not found) can be queried for knowledge gaps
- Filter by `answer_id` and `vote` for gap analysis
- Tests: `test_list_feedback_client_admin`, `test_list_feedback_filter_by_answer`, `test_list_feedback_filter_by_vote`

## Implementation Summary

### Files Created
| File | Purpose |
|------|---------|
| `alembic/versions/011_feedback.py` | Migration: answers + answer_feedback tables, RLS, grants |
| `app/models/feedback.py` | Answer, AnswerFeedback models with constraints |
| `app/schemas/feedback.py` | Request/response schemas with vote validation |
| `app/routes/feedback.py` | POST/PATCH/GET feedback endpoints |
| `tests/test_feedback.py` | 16 tests covering CRUD, auth, isolation |

### Files Modified
| File | Change |
|------|--------|
| `app/models/__init__.py` | Export Answer, AnswerFeedback |
| `app/main.py` | Register feedback router |
| `app/auth/permissions.py` | Add feedback endpoints to ROLE_MATRIX |
| `tests/isolation_manifest.py` | Add feedback routes for coverage guard |

### RLS & Security
- ✅ `answers` table: FORCE RLS on `tenant_id`
- ✅ `answer_feedback` table: FORCE RLS on `tenant_id`
- ✅ `vaultiq_app`: CRUD on both (NOBYPASSRLS)
- ✅ `vaultiq_super_admin`: SELECT only (platform analytics)
- ✅ Employee: can only create/update/retrieve own feedback
- ✅ Client Admin: can view all feedback in tenant, list with filters
- ✅ Super Admin: DENIED on all feedback endpoints (403)

### Database Constraints
- ✅ Unique constraint: one vote per user per answer (uq_feedback_answer_user)
- ✅ Check constraint: vote ∈ {1, -1} (ck_feedback_vote)
- ✅ Comment max 500 chars (validated in schema)
- ✅ CASCADE deletes on tenant/user/answer

## Tests Status
| Test Suite | Status |
|------------|--------|
| `test_tenant.py` | 8 passed |
| `test_auth.py` | 18 passed |
| `test_documents.py` | 13 passed |
| `test_rls.py` | 15 passed |
| `test_tenant_lifecycle.py` | 21 passed |
| `test_permissions.py` | 21 passed |
| `test_isolation_suite.py` | 36 passed |
| `test_tenant_context.py` | 5 passed |
| `test_feedback.py` | **16 passed** (NEW) |
| **Total** | **153 passed** |

## Common Mistakes Checklist

- [x] Vote validation at schema level (not just DB constraint)
- [x] Unique constraint prevents duplicate votes
- [x] RLS on both tables with proper grants
- [x] Super Admin explicitly denied on feedback endpoints
- [x] Cross-tenant isolation proven (test_cross_tenant_feedback_isolation)
- [x] Employee sees only own feedback; Client Admin sees all
- [x] Comment length limit enforced (500 chars)
- [x] Feedback is changeable (PATCH endpoint)
- [x] Route coverage guard includes feedback endpoints

## Known Limitations / Follow-ups

1. **Answer creation**: Currently no endpoint to create Answer records. Search integration (VQ-204) will create Answers when returning results.
2. **Knowledge gaps query**: VQ-302 will need to query `answers WHERE answer_text IS NULL AND feedback.vote = -1`
3. **Question deduplication**: Same question asked twice creates two Answer rows (by design - different contexts)
4. **Confidence scoring**: Simple heuristic (1.0/0.5/NULL) - defer ML-based confidence

## Gate 6 Evidence (Live Container)

**Prerequisites**: Database migrated, app running at `http://127.0.0.1:8000`

### Test Commands
```bash
# 1. Login as Super Admin, create tenant
# 2. Create invite, accept as Client Admin
# 3. Login as Employee, create Answer via DB (or search when VQ-204 merged)
# 4. Submit feedback
curl -X POST http://127.0.0.1:8000/answers/{answer_id}/feedback \
  -H "Authorization: Bearer $EMP_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"vote": -1, "comment": "Answer was incorrect"}'

# 5. Update feedback
curl -X PATCH http://127.0.0.1:8000/answers/{answer_id}/feedback \
  -H "Authorization: Bearer $EMP_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"vote": 1}'

# 6. Client Admin lists all feedback
curl -X GET "http://127.0.0.1:8000/answers/feedback?vote=-1" \
  -H "Authorization: Bearer $ADMIN_TOKEN"

# 7. Cross-tenant isolation test
# (Run test_cross_tenant_feedback_isolation via pytest)
```

### Expected Results
- Employee can submit/update own feedback only
- Client Admin sees all feedback in tenant with filters
- Super Admin gets 403 on all feedback endpoints
- Cross-tenant requests return 404 (RLS enforcement)
- All 153 tests pass

## Approval
All acceptance criteria addressed. Gates 1-4 complete. Ready for Gate 5 (code review) and Gate 6 (live verify).