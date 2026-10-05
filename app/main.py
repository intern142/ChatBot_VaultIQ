from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routes.auth import router as auth_router
from app.routes.documents import router as documents_router
from app.routes.admin import router as admin_router
from app.routes.invite import router as invite_router
from app.routes.users import router as users_router
from app.routes.feedback import router as feedback_router
from app.routes.search import router as search_router

app = FastAPI(
    title="VaultIQ API",
    description="Multi-tenant documents-only Q&A system",
    version="0.1.0",
)

_origins = [
    origin.strip()
    for origin in get_settings().CORS_ALLOWED_ORIGINS.split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(auth_router)
app.include_router(documents_router)
app.include_router(admin_router)
app.include_router(invite_router)
app.include_router(users_router)
app.include_router(feedback_router)
app.include_router(search_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
