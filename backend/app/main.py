"""
PurpleSol — AI Retail Intelligence Platform
Main FastAPI Application
"""

from __future__ import annotations

import structlog
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse

from app.config import settings
from app.database import init_db, close_db
from app.api.stores import router as stores_router
from app.api.events import router as events_router
from app.api.analytics import router as analytics_router
from app.api.websocket import router as ws_router
from app.api.video import router as video_router

# ── Logging ──────────────────────────────────────────────────────
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.dev.ConsoleRenderer() if not settings.is_production
        else structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()


# ── Lifecycle ────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle: startup and shutdown."""
    logger.info(
        "Starting PurpleSol API",
        version=settings.app_version,
        env=settings.app_env,
    )
    await init_db()
    logger.info("Database initialized")
    yield
    await close_db()
    logger.info("PurpleSol API shutdown")


# ── App ──────────────────────────────────────────────────────────
app = FastAPI(
    title="PurpleSol — Retail Intelligence Platform",
    description=(
        "AI-powered platform that converts CCTV footage into "
        "real-time retail analytics and customer journey intelligence."
    ),
    version=settings.app_version,
    lifespan=lifespan,
    default_response_class=ORJSONResponse,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS ─────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ──────────────────────────────────────────────────────
app.include_router(stores_router)
app.include_router(events_router)
app.include_router(analytics_router)
app.include_router(ws_router)
app.include_router(video_router)


# ── Health Check ─────────────────────────────────────────────────
@app.get("/", tags=["Health"])
async def root():
    """Health check endpoint."""
    return {
        "name": "PurpleSol API",
        "version": settings.app_version,
        "status": "healthy",
        "env": settings.app_env,
    }


@app.get("/health", tags=["Health"])
async def health():
    """Detailed health check."""
    return {
        "status": "healthy",
        "database": "connected",
        "version": settings.app_version,
    }
