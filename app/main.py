from fastapi import FastAPI
from app.routes.auth import router as auth_router
from app.routes.documents import router as documents_router
from app.routes.admin import router as admin_router

app = FastAPI(
    title="VaultIQ API",
    description="Multi-tenant documents-only Q&A system",
    version="0.1.0",
)

app.include_router(auth_router)
app.include_router(documents_router)
app.include_router(admin_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
