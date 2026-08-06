from fastapi import FastAPI

from app.shared.config import settings

app = FastAPI(
    title=settings.app.name,
    version=settings.app.version,
    debug=settings.app.debug,
)


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok", "environment": settings.app.environment}
