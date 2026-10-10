"""PurpleSol Backend Configuration.

All settings come from environment variables (or a local ``.env`` file in
development). Production refuses to start with insecure defaults; see
``Settings.validate_for_production``.
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

INSECURE_SECRET = "dev-secret-key-change-me"


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        populate_by_name=True,
        extra="ignore",
    )

    # ── Application ──────────────────────────────────────────────
    app_name: str = "PurpleSol"
    app_version: str = "2.0.0"
    app_env: str = Field(default="development", alias="APP_ENV")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    secret_key: str = Field(default=INSECURE_SECRET, alias="SECRET_KEY")

    # ── Database ─────────────────────────────────────────────────
    database_url: str = Field(
        default="sqlite+aiosqlite:///./purplesol.db",
        alias="DATABASE_URL",
    )
    db_echo: bool = Field(default=False, alias="DB_ECHO")
    # Create tables with metadata.create_all at startup instead of running
    # Alembic. Only intended for throwaway test databases.
    db_auto_create: bool = Field(default=False, alias="DB_AUTO_CREATE")

    # ── API / security ───────────────────────────────────────────
    api_cors_origins: str = Field(default="http://localhost:3000", alias="API_CORS_ORIGINS")
    session_ttl_hours: int = Field(default=24 * 7, alias="SESSION_TTL_HOURS")
    cookie_secure: Optional[bool] = Field(default=None, alias="COOKIE_SECURE")
    cookie_samesite: str = Field(default="lax", alias="COOKIE_SAMESITE")
    # Optional machine-to-machine key for POST /api/events ingestion.
    ingest_api_key: Optional[str] = Field(default=None, alias="INGEST_API_KEY")
    # Bootstrap admin, created at startup only when the users table is empty.
    admin_email: Optional[str] = Field(default=None, alias="ADMIN_EMAIL")
    admin_password: Optional[str] = Field(default=None, alias="ADMIN_PASSWORD")
    login_rate_limit_per_minute: int = Field(default=10, alias="LOGIN_RATE_LIMIT_PER_MINUTE")
    upload_rate_limit_per_hour: int = Field(default=60, alias="UPLOAD_RATE_LIMIT_PER_HOUR")

    @property
    def cors_origins(self) -> List[str]:
        return [o.strip() for o in self.api_cors_origins.split(",") if o.strip()]

    @property
    def use_secure_cookies(self) -> bool:
        if self.cookie_secure is not None:
            return self.cookie_secure
        return self.is_production

    # ── Object storage ───────────────────────────────────────────
    # "local" stores files under STORAGE_LOCAL_DIR (dev / single host only).
    # "s3" uses any S3-compatible service (AWS S3, Cloudflare R2, MinIO...).
    storage_backend: str = Field(default="local", alias="STORAGE_BACKEND")
    storage_local_dir: str = Field(default="./storage", alias="STORAGE_LOCAL_DIR")
    s3_bucket: Optional[str] = Field(default=None, alias="S3_BUCKET")
    s3_endpoint_url: Optional[str] = Field(default=None, alias="S3_ENDPOINT_URL")
    s3_region: str = Field(default="auto", alias="S3_REGION")
    s3_access_key_id: Optional[str] = Field(default=None, alias="S3_ACCESS_KEY_ID")
    s3_secret_access_key: Optional[str] = Field(default=None, alias="S3_SECRET_ACCESS_KEY")
    s3_presign_expiry_seconds: int = Field(default=3600, alias="S3_PRESIGN_EXPIRY_SECONDS")

    # ── Uploads ──────────────────────────────────────────────────
    max_upload_bytes: int = Field(default=2 * 1024**3, alias="MAX_UPLOAD_BYTES")
    allowed_video_extensions: str = Field(
        default=".mp4,.mov,.m4v,.mkv,.avi,.webm", alias="ALLOWED_VIDEO_EXTENSIONS"
    )
    video_retention_days: int = Field(default=30, alias="VIDEO_RETENTION_DAYS")

    @property
    def video_extensions(self) -> List[str]:
        return [e.strip().lower() for e in self.allowed_video_extensions.split(",") if e.strip()]

    # ── CV processing ────────────────────────────────────────────
    yolo_model: str = Field(default="yolo11n.pt", alias="YOLO_MODEL")
    yolo_confidence: float = Field(default=0.35, alias="YOLO_CONFIDENCE")
    yolo_iou: float = Field(default=0.5, alias="YOLO_IOU")
    yolo_imgsz: int = Field(default=640, alias="YOLO_IMGSZ")
    cv_device: str = Field(default="auto", alias="CV_DEVICE")
    analysis_fps: float = Field(default=5.0, alias="ANALYSIS_FPS")
    max_video_seconds: int = Field(default=4 * 3600, alias="MAX_VIDEO_SECONDS")

    # ── Worker ───────────────────────────────────────────────────
    worker_poll_seconds: float = Field(default=3.0, alias="WORKER_POLL_SECONDS")
    worker_heartbeat_seconds: float = Field(default=10.0, alias="WORKER_HEARTBEAT_SECONDS")
    # A running job whose heartbeat is older than this is considered orphaned
    # (worker crashed / redeployed) and is re-queued.
    job_stale_after_seconds: int = Field(default=180, alias="JOB_STALE_AFTER_SECONDS")
    job_max_attempts: int = Field(default=3, alias="JOB_MAX_ATTEMPTS")
    job_timeout_seconds: int = Field(default=6 * 3600, alias="JOB_TIMEOUT_SECONDS")
    worker_tmp_dir: str = Field(default="/tmp/purplesol-worker", alias="WORKER_TMP_DIR")

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    def validate_for_production(self) -> List[str]:
        """Return a list of configuration problems that block production."""
        problems: List[str] = []
        if not self.is_production:
            return problems
        if self.secret_key == INSECURE_SECRET or len(self.secret_key) < 32:
            problems.append("SECRET_KEY must be set to a random value of at least 32 characters")
        if self.database_url.startswith("sqlite"):
            problems.append("DATABASE_URL must point to PostgreSQL in production")
        if self.storage_backend == "s3" and not self.s3_bucket:
            problems.append("S3_BUCKET is required when STORAGE_BACKEND=s3")
        if "*" in self.cors_origins:
            problems.append("API_CORS_ORIGINS must not contain '*' in production")
        return problems


settings = Settings()
