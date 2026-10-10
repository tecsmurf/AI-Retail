"""PurpleSol API application."""

from __future__ import annotations

import time
import uuid
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import func, select

from app.api.analytics import router as analytics_router
from app.api.auth import router as auth_router
from app.api.auth import users_router
from app.api.events import router as events_router
from app.api.pos import router as pos_router
from app.api.stores import router as stores_router
from app.api.system import request_metrics
from app.api.system import router as system_router
from app.api.videos import router as videos_router
from app.config import settings
from app.database import async_session, close_db, create_all
from app.logging_setup import configure_logging
from app.models.user import ROLE_ADMIN, User
from app.security import hash_password

configure_logging()
logger = structlog.get_logger("purplesol.api")


async def bootstrap_admin() -> None:
    """Create the first admin from ADMIN_EMAIL/ADMIN_PASSWORD when no user exists."""
    if not (settings.admin_email and settings.admin_password):
        return
    async with async_session() as db:
        if (await db.execute(select(func.count()).select_from(User))).scalar():
            return
        db.add(User(email=settings.admin_email.strip().lower(), password_hash=hash_password(settings.admin_password),
                    role=ROLE_ADMIN, is_active=True))
        await db.commit()
        logger.info("bootstrap_admin_created")


@asynccontextmanager
async def lifespan(app: FastAPI):
    problems = settings.validate_for_production()
    if problems:
        for p in problems:
            logger.error("config_invalid", problem=p)
        raise RuntimeError("Refusing to start with an insecure production configuration: " + "; ".join(problems))
    if settings.db_auto_create:
        await create_all()
    await bootstrap_admin()
    logger.info("api_started", version=settings.app_version, env=settings.app_env)
    yield
    await close_db()


app = FastAPI(
    title="PurpleSol API",
    description="Anonymous retail analytics from existing CCTV footage.",
    version=settings.app_version,
    lifespan=lifespan,
    docs_url=None if settings.is_production else "/docs",
    redoc_url=None,
    openapi_url=None if settings.is_production else "/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-PurpleSol-CSRF", "X-API-Key", "X-Request-ID"],
    expose_headers=["X-Request-ID"],
)


@app.middleware("http")
async def request_context(request: Request, call_next):
    rid = request.headers.get("x-request-id", "")[:64] or uuid.uuid4().hex
    structlog.contextvars.bind_contextvars(request_id=rid)
    started = time.perf_counter()
    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
    except Exception:
        logger.exception("unhandled_error", method=request.method, path=request.url.path)
        response = JSONResponse({"detail": "Internal server error", "request_id": rid}, status_code=500)
    finally:
        ms = (time.perf_counter() - started) * 1000
        route = request.scope.get("route")
        route_path = getattr(route, "path", "unmatched")
        request_metrics.observe(f"{request.method} {route_path}", status, ms)
        if not request.url.path.startswith("/health"):
            logger.info("request", method=request.method, route=route_path, status=status, ms=round(ms, 1),
                        user_id=getattr(request.state, "user_id", None))
        structlog.contextvars.clear_contextvars()
    response.headers["X-Request-ID"] = rid
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


for r in (system_router, auth_router, users_router, stores_router, events_router, analytics_router,
          videos_router, pos_router):
    app.include_router(r)


@app.get("/", include_in_schema=False)
async def root():
    return {"name": "PurpleSol API", "version": settings.app_version, "health": "/health/ready"}
