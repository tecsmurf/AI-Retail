"""Video upload and processing-job schemas."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class VideoCreate(BaseModel):
    store_id: uuid.UUID
    camera_id: uuid.UUID
    filename: str = Field(..., min_length=1, max_length=300)
    size_bytes: int = Field(..., gt=0)
    content_type: str = Field("video/mp4", max_length=100)
    # When recording started (with offset). Omit to use the upload time,
    # which is flagged as an assumption on the job.
    recorded_start: Optional[datetime] = None

    @field_validator("recorded_start")
    @classmethod
    def _aware(cls, v: Optional[datetime]) -> Optional[datetime]:
        if v is None:
            return v
        if v.tzinfo is None:
            raise ValueError("recorded_start must include a time zone offset")
        return v.astimezone(UTC).replace(tzinfo=None)


class UploadInstructions(BaseModel):
    method: str
    url: str
    headers: Dict[str, str]
    direct_to_storage: bool


class VideoResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    store_id: uuid.UUID
    camera_id: uuid.UUID
    original_filename: str
    content_type: Optional[str] = None
    size_bytes: Optional[int] = None
    status: str
    recorded_start: Optional[datetime] = None
    recorded_start_assumed: bool = False
    probe: Optional[dict] = None
    created_at: datetime
    uploaded_at: Optional[datetime] = None


class VideoCreated(BaseModel):
    video: VideoResponse
    upload: UploadInstructions


class VideoComplete(BaseModel):
    start_processing: bool = True
    pipeline: Optional[dict] = None


class PipelineOverrides(BaseModel):
    analysis_fps: Optional[float] = Field(None, gt=0, le=30)
    detector_confidence: Optional[float] = Field(None, ge=0.05, le=0.9)
    track_activation_threshold: Optional[float] = Field(None, ge=0.1, le=0.9)
    lost_track_seconds: Optional[float] = Field(None, ge=0.5, le=30)
    zone_enter_min_s: Optional[float] = Field(None, ge=0, le=60)
    zone_exit_grace_s: Optional[float] = Field(None, ge=0, le=60)
    queue_enter_min_s: Optional[float] = Field(None, ge=0, le=300)


class JobCreate(BaseModel):
    video_id: uuid.UUID
    pipeline: Optional[PipelineOverrides] = None
    allow_duplicate: bool = False


class JobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    store_id: uuid.UUID
    camera_id: uuid.UUID
    video_id: uuid.UUID
    status: str
    cancel_requested: bool
    progress: float
    stage: Optional[str] = None
    attempts: int
    max_attempts: int
    created_at: datetime
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    heartbeat_at: Optional[datetime] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    error_retryable: Optional[bool] = None
    config: Optional[dict] = None
    model_name: Optional[str] = None
    model_sha256: Optional[str] = None
    pipeline_version: Optional[str] = None
    results: Optional[dict] = None
    artifacts: Optional[dict] = None
    video_filename: Optional[str] = None
    camera_code: Optional[str] = None


class JobPage(BaseModel):
    total: int
    items: List[JobResponse]
