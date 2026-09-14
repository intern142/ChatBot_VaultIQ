from fastapi import FastAPI

app = FastAPI(
    title="VaultIQ API",
    description="Multi-tenant documents-only Q&A system",
    version="0.1.0",
)


@app.get("/health")
async def health():
    return {"status": "ok"}
