# Review Checklist & Common Mistakes

Use this checklist for every story before opening a PR.

---

## Review Checklist

### Code Quality
- [ ] Code follows project style conventions
- [ ] No hardcoded secrets, passwords, or connection strings
- [ ] No `print()` or `console.log` left in production code
- [ ] Functions are focused and not too long
- [ ] No unused imports or variables
- [ ] Error handling is present and appropriate

### Database & Migrations
- [ ] Migration is reversible (upgrade + downgrade)
- [ ] Migration tested: upgrade → downgrade → re-upgrade
- [ ] No data loss on downgrade
- [ ] Indexes added for frequently queried columns
- [ ] Foreign keys have appropriate ON DELETE behavior
- [ ] Constraints are enforced at DB level (not just app level)

### Security
- [ ] Input validation on all user-facing endpoints
- [ ] SQL injection not possible (use ORM/parameterized queries)
- [ ] Authentication required where needed
- [ ] Authorization/permissions enforced
- [ ] Sensitive data not logged
- [ ] Secrets loaded from environment variables, not hardcoded

### API Design
- [ ] Consistent response format across endpoints
- [ ] Proper HTTP status codes used
- [ ] Request/response schemas validated with Pydantic
- [ ] API documentation (OpenAPI) is accurate

### Testing
- [ ] Unit tests written for new logic
- [ ] Edge cases covered
- [ ] Negative tests (error paths) included
- [ ] All tests pass locally
- [ ] No test depends on external services without mocking

### Multi-Tenancy (VaultIQ specific)
- [ ] New tables have `tenant_id` column (unless exempt)
- [ ] RLS policies applied to tenant-scoped tables
- [ ] Queries respect tenant context
- [ ] Cross-tenant data access is blocked
- [ ] Super admin bypass works correctly

### Files & Structure
- [ ] New files in correct directory structure
- [ ] `__init__.py` exports updated if needed
- [ ] Config changes reflected in `.env.example`
- [ ] Dependencies added to `requirements.txt` and `pyproject.toml`
- [ ] `.gitignore` updated if new artifact types

---

## Common Mistakes

### Database
- [ ] Forgetting `ON DELETE CASCADE` or `ON DELETE RESTRICT` on foreign keys
- [ ] Not adding indexes on foreign key columns
- [ ] Migration not tested with downgrade path
- [ ] Using `nullable=False` without a default value
- [ ] Forgetting `server_default` vs `default` (DB vs app level)

### SQLAlchemy
- [ ] Using sync session instead of async session in async context
- [ ] Not calling `await session.commit()` after changes
- [ ] Accessing relationships without eager loading (N+1 query problem)
- [ ] Using `Column` instead of `mapped_column` (SQLAlchemy 2.0 style)

### FastAPI
- [ ] Not using `Depends(get_db)` for database sessions
- [ ] Missing `response_model` on endpoints
- [ ] Not handling 404/400/422 errors properly
- [ ] Circular imports between routes and models

### Pydantic
- [ ] Missing `Field` constraints (min_length, max_length, gt, lt)
- [ ] Not using `from_attributes = True` for ORM model responses
- [ ] Mutable default arguments in schemas

### Security
- [ ] Hardcoded JWT secrets in source code
- [ ] Returning full error details to client in production
- [ ] Not hashing passwords before storing
- [ ] Missing rate limiting on auth endpoints

### Git
- [ ] Committing `.env` file with secrets
- [ ] Committing `__pycache__` or `.pyc` files
- [ ] Large files committed (use Git LFS)
- [ ] Inconsistent commit messages
