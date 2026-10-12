"""Video assets, durable processing jobs, occupancy samples, worker heartbeats."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, utcnow

JOB_QUEUED = "queued"
JOB_RUNNING = "running"
JOB_COMPLETED = "completed"
JOB_FAILED = "failed"
JOB_CANCELLED = "cancelled"
JOB_STATES = (JOB_QUEUED, JOB_RUNNING, JOB_COMPLETED, JOB_FAILED, JOB_CANCELLED)
JOB_TERMINAL = (JOB_COMPLETED, JOB_FAILED, JOB_CANCELLED)

VIDEO_PENDING = "pending_upload"
VIDEO_UPLOADED = "uploaded"
VIDEO_DELETED = "deleted"


class VideoAsset(Base):
    """A source video stored in object storage (never on an app container)."""

    __tablename__ = "video_assets"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    store_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("stores.id", ondelete="CASCADE"), index=True)
    camera_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("cameras.id", ondelete="CASCADE"), index=True)
    storage_key: Mapped[str] = mapped_column(String(500), unique=True)
    original_filename: Mapped[str] = mapped_column(String(300))
    content_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    size_bytes: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default=VIDEO_PENDING, index=True)
    # When the footage was recorded (naive UTC). Event timestamps are
    # recorded_start + video offset. ``recorded_start_assumed`` is True when the
    # uploader did not provide it and the upload time was used instead.
    recorded_start: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    recorded_start_assumed: Mapped[bool] = mapped_column(Boolean, default=False)
    probe: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    uploaded_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class ProcessingJob(Base):
    """Durable video-processing job; the database row *is* the queue entry."""

    __tablename__ = "processing_jobs"
    __table_args__ = (Index("ix_jobs_status_created", "status", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    store_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("stores.id", ondelete="CASCADE"), index=True)
    camera_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("cameras.id", ondelete="CASCADE"), index=True)
    video_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("video_assets.id", ondelete="CASCADE"), index=True)

    status: Mapped[str] = mapped_column(String(20), default=JOB_QUEUED, index=True)
    cancel_requested: Mapped[bool] = mapped_column(Boolean, default=False)
    progress: Mapped[float] = mapped_column(Float, default=0.0)  # 0..1
    stage: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    locked_by: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    heartbeat_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    error_code: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error_retryable: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)

    # Snapshot of the processing configuration (thresholds, sampling, zones,
    # entry line, camera config version) so results are reproducible.
    config: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    model_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    model_sha256: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    pipeline_version: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    # Summary statistics: frames, detections, tracks, events, timings, warnings.
    results: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    # Storage keys of artifacts (tracks.jsonl.gz, annotated snapshots).
    artifacts: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    video: Mapped[VideoAsset] = relationship()


class OccupancySample(Base):
    """Number of tracked people inside a zone at a point in time."""

    __tablename__ = "occupancy_samples"
    __table_args__ = (Index("ix_occupancy_store_zone_ts", "store_id", "zone_name", "timestamp"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    store_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("stores.id", ondelete="CASCADE"), index=True)
    job_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("processing_jobs.id", ondelete="CASCADE"), index=True
    )
    camera_code: Mapped[str] = mapped_column(String(50))
    zone_name: Mapped[str] = mapped_column(String(200))
    zone_type: Mapped[str] = mapped_column(String(50))
    timestamp: Mapped[datetime] = mapped_column(DateTime)
    count: Mapped[int] = mapped_column(Integer)


class WorkerHeartbeat(Base):
    """Liveness record written by each worker process."""

    __tablename__ = "worker_heartbeats"

    worker_id: Mapped[str] = mapped_column(String(200), primary_key=True)
    hostname: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    current_job_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid, nullable=True)
    model_loaded: Mapped[bool] = mapped_column(Boolean, default=False)
    model_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    device: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    rss_mb: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    jobs_completed: Mapped[int] = mapped_column(Integer, default=0)
    jobs_failed: Mapped[int] = mapped_column(Integer, default=0)
    version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
