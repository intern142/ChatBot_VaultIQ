from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes.auth import router as auth_router
from app.routes.documents import router as documents_router
from app.routes.admin import router as admin_router
from app.routes.invite import router as invite_router
from app.routes.dashboard import router as dashboard_router
from app.routes.users import router as users_router
from app.routes.feedback import router as feedback_router
from app.routes.search import router as search_router
from app.routes.answers import router as answers_router
from app.routes.admin_dashboard import router as admin_dashboard_router
from app.config import get_settings

app = FastAPI(
    title="VaultIQ API",
    description="Multi-tenant documents-only Q&A system",
    version="0.1.0",
)

settings = get_settings()

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ALLOWED_ORIGINS.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(documents_router)
app.include_router(admin_router)
app.include_router(invite_router)
app.include_router(users_router)
app.include_router(feedback_router)
app.include_router(search_router)
app.include_router(answers_router)
app.include_router(admin_dashboard_router)


@app.get("/health")
async def health():
    return {"status": "ok"}