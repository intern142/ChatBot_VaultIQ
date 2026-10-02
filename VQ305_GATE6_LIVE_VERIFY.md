# VQ-305 Gate 6: Live Container Verification

## Test Environment
- **Date**: 2026-10-02
- **API Base URL**: http://127.0.0.1:8000
- **Database**: PostgreSQL 16 (Docker: vaultiq-db, port 5433)
- **Tenants**: POLA, POLB with client_admin and employee users

## Verified Endpoints (Live)

### 1. POST /answers/{answer_id}/feedback — Create Feedback
```bash
curl -X POST http://127.0.0.1:8000/answers/f2502cbc-30f4-4484-9c57-fa7755c5dc9c/feedback \
  -H "Authorization: Bearer $EMP_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"vote": 1, "comment": "Helpful answer"}'
```
**Result**: ✅ 201 Created
```json
{"id":"9cca7af3-...","answer_id":"f2502cbc-...","user_id":"01970112-...","vote":1,"comment":"Helpful answer","created_at":"...","updated_at":"..."}
```

### 2. PATCH /answers/{answer_id}/feedback — Update Feedback
```bash
curl -X PATCH http://127.0.0.1:8000/answers/f2502cbc-30f4-4484-9c57-fa7755c5dc9c/feedback \
  -H "Authorization: Bearer $EMP_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"vote": -1, "comment": "Changed mind"}'
```
**Result**: ✅ 200 OK (vote changed, updated_at updated)

### 3. GET /answers/{answer_id}/feedback — Get Own Feedback (Employee)
```bash
curl -X GET http://127.0.0.1:8000/answers/f2502cbc-30f4-4484-9c57-fa7755c5dc9c/feedback \
  -H "Authorization: Bearer $EMP_TOKEN"
```
**Result**: ✅ 200 OK (returns own feedback only)

### 4. GET /answers/feedback — List All Feedback (Client Admin)
```bash
curl -X GET "http://127.0.0.1:8000/answers/feedback?vote=-1" \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```
**Result**: ✅ 200 OK
```json
{"feedback":[{"id":"9cca7af3-...","answer_id":"f2502cbc-...","user_id":"01970112-...","vote":-1,"comment":"Changed mind",...}],"total":1,"page":1,"page_size":20}
```

### 5. Cross-Tenant Isolation — Employee A cannot access Employee B's answer
- Employee A (POLB) tries to POST feedback on Answer B (POLA)
- **Result**: ✅ 404 Not Found (RLS blocks access)

### 6. Duplicate Feedback Prevention
- Same employee tries to POST feedback twice on same answer
- **Result**: ✅ 409 Conflict ("Feedback already exists... Use PATCH to update")

### 7. Super Admin Denied
- Super Admin tries to POST feedback
- **Result**: ✅ 403 Forbidden (ROLE_MATRIX enforcement)

## Test Suite Results (Live Container)

| Test Suite | Status | Notes |
|------------|--------|-------|
| `test_feedback.py` | 16/16 passed | All CRUD, auth, isolation tests |
| `test_isolation_suite.py` (LIVE_BASE_URL) | 36/36 passed | Route coverage guard includes feedback endpoints |
| `test_permissions.py` | 21/21 passed | Feedback endpoints in ROLE_MATRIX |

**Total**: 153 tests passing (137 original + 16 feedback)

## Acceptance Criteria Verification

| AC | Requirement | Live Verified |
|----|-------------|---------------|
| AC1 | Thumbs up/down + comment; one vote/user/answer, changeable | ✅ POST + PATCH verified |
| AC2 | Stored with tenant, user, answer, source docs | ✅ RLS + FKs + arrays verified |
| AC3 | Available to Client Admin dashboard, knowledge gaps | ✅ GET /answers/feedback with filters |

## Evidence Files
- `VQ305_GATE6_LIVE_VERIFY.md` — This document
- `uvicorn_gate6.log` / `uvicorn_gate6_err.log` — Server logs
- `benchmark_results.json` — Not applicable (no latency benchmark for feedback)

## Conclusion
✅ **Gate 6 PASSED** — All feedback endpoints functional on live container with:
- Correct role-based access (Employee own, Client Admin all, Super Admin denied)
- Cross-tenant isolation enforced by RLS (404 on cross-tenant access)
- Vote validation (1/-1), comment length (500 chars), unique constraint
- All 153 tests passing including isolation suite against live container

Ready for Gate 7 (Demo).