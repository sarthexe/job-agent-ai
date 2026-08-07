from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.job import router as job_router
from app.shared.config import settings
from app.shared.database import close_engine
from app.shared.exceptions import AppError
from app.shared.logging import RequestIDMiddleware, get_logger, setup_logging
from app.system import router as system_router

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


@app.exception_handler(AppError)
async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
    """Map domain errors to meaningful HTTP responses."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.message, "code": exc.code},
    )


app.add_middleware(RequestIDMiddleware)
app.include_router(system_router)
app.include_router(job_router)
