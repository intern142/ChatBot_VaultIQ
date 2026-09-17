from fastapi import FastAPI
from app.routes.auth import router as auth_router

app = FastAPI(
    title="VaultIQ API",
    description="Multi-tenant documents-only Q&A system",
    version="0.1.0",
)

app.include_router(auth_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
