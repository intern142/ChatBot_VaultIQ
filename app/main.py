from fastapi import FastAPI
from app.routes.auth import router as auth_router
from app.routes.documents import router as documents_router
from app.routes.admin import router as admin_router
from app.routes.invite import router as invite_router
from app.routes.tenant import router as tenant_router
from app.routes.public import router as public_router
from app.routes.dashboard import router as dashboard_router
from app.routes.users import router as users_router
from app.routes.feedback import router as feedback_router
from app.routes.search import router as search_router
from app.routes.answers import router as answers_router
from app.routes.admin_dashboard import router as admin_dashboard_router
from app.routes.audit import router as audit_router

app = FastAPI(
    title="VaultIQ API",
    version="1.0.0",
    description="Multi-tenant document Q&A with strict tenant isolation",
)

app.include_router(auth_router)
app.include_router(documents_router)
app.include_router(admin_router)
app.include_router(invite_router)
app.include_router(tenant_router)
app.include_router(public_router)
app.include_router(dashboard_router)
app.include_router(users_router)
app.include_router(feedback_router)
app.include_router(search_router)
app.include_router(answers_router)
app.include_router(admin_dashboard_router)
app.include_router(audit_router)


@app.get("/health")
async def health():
    return {"status": "ok"}