"""PurpleSol Backend Configuration."""

from __future__ import annotations

import os
from typing import List

from pydantic_settings import BaseSettings
from pydantic import Field, ConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # ── Application ──────────────────────────────────────────────
    app_name: str = "PurpleSol"
    app_version: str = "1.0.0"
    app_env: str = Field(default="development", alias="APP_ENV")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    secret_key: str = Field(default="dev-secret-key", alias="SECRET_KEY")

    # ── Database ─────────────────────────────────────────────────
    database_url: str = Field(
        default="sqlite+aiosqlite:///./purplesol.db",
        alias="DATABASE_URL",
    )

    # ── Redis ────────────────────────────────────────────────────
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        alias="REDIS_URL",
    )

    # ── API ──────────────────────────────────────────────────────
    api_host: str = Field(default="0.0.0.0", alias="API_HOST")
    api_port: int = Field(default=8000, alias="API_PORT")
    api_cors_origins: str = Field(
        default="http://localhost:3000",
        alias="API_CORS_ORIGINS",
    )

    @property
    def cors_origins(self) -> List[str]:
        return [o.strip() for o in self.api_cors_origins.split(",")]

    # ── CV Processing ────────────────────────────────────────────
    yolo_model: str = Field(default="yolo11n.pt", alias="YOLO_MODEL")
    yolo_confidence: float = Field(default=0.5, alias="YOLO_CONFIDENCE")
    tracker_type: str = Field(default="bytetrack", alias="TRACKER_TYPE")
    max_concurrent_streams: int = Field(default=4, alias="MAX_CONCURRENT_STREAMS")

    # ── Paths ────────────────────────────────────────────────────
    upload_dir: str = Field(default="uploads", alias="UPLOAD_DIR")
    model_dir: str = Field(default="models", alias="MODEL_DIR")

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"





settings = Settings()
