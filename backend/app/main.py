from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.shared.config import settings
from app.shared.database import close_engine
from app.shared.logging import RequestIDMiddleware, get_logger, setup_logging

setup_logging(settings)
logger = get_logger("app.main")


@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info(
        "application_started",
        environment=settings.app.environment,
        log_format=settings.logging.format,
    )
    yield
    await close_engine()
    logger.info("application_stopped")


app = FastAPI(
    title=settings.app.name,
    version=settings.app.version,
    debug=settings.app.debug,
    lifespan=lifespan,
)
app.add_middleware(RequestIDMiddleware)


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok", "environment": settings.app.environment}
