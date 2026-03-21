import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import ProgrammingError

from app.db import check_connection, database_url, dispose_engine
from app.routers.auth import router as auth_router
from app.routers.generate import router as generate_router
from app.routers.infer_schema import router as infer_schema_router
from app.routers.observability import router as observability_router
from app.routers.profile import router as profile_router
from app.routers.stats import router as stats_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    if database_url():
        state, detail = await check_connection()
        if state == "error":
            logger.warning("Database unavailable at startup: %s", detail)
    yield
    await dispose_engine()


def create_app() -> FastAPI:
    app = FastAPI(title="Converter Agent MVP", version="0.1.0", lifespan=lifespan)

    # For MVP: allow all origins by default.
    # In production you should tighten this.
    cors_origins = os.getenv("CORS_ALLOW_ORIGINS", "*")
    if cors_origins.strip() == "*":
        allow_origins = ["*"]
    else:
        # Comma-separated origins list.
        allow_origins = [o.strip() for o in cors_origins.split(",") if o.strip()]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allow_origins,
        # For MVP мы не используем cookie/credentials в fetch, поэтому
        # отключаем allow_credentials, чтобы не получить некорректный
        # CORS заголовок при allow_origins="*".
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(ProgrammingError)
    async def programming_error_handler(_request: Request, exc: ProgrammingError) -> JSONResponse:
        """Missing tables / bad SQL → clearer than generic 500 (e.g. migrations not applied)."""
        logger.exception("Database programming error: %s", exc)
        return JSONResponse(
            status_code=503,
            content={
                "detail": "Ошибка схемы БД (часто не применены миграции). Проверьте DATABASE_URL и backend/migrations.",
            },
        )

    @app.get("/health")
    async def health():
        state, detail = await check_connection()
        return {"status": "ok", "database": {"state": state, "detail": detail}}

    app.include_router(auth_router)
    app.include_router(generate_router)
    app.include_router(infer_schema_router)
    app.include_router(profile_router)
    app.include_router(observability_router)
    app.include_router(stats_router)
    return app


app = create_app()

#PotJoke wuz here