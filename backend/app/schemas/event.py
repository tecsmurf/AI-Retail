"""Event schemas."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

IngestEventType = Literal[
    "ENTRY", "EXIT", "ZONE_ENTER", "ZONE_EXIT", "QUEUE_ENTER", "QUEUE_EXIT", "QUEUE_COMPLETED", "QUEUE_ABANDONED"
]


class EventCreate(BaseModel):
    """External event ingestion.

    ``event_key`` is the idempotency key: re-sending an event with the same
    key for the same store is a no-op. If omitted, a key is derived from the
    event's content, so exact duplicates are still dropped.
    ``timestamp`` must include a time zone offset (or 'Z').
    """

    event_type: IngestEventType
    customer_id: str = Field(..., min_length=1, max_length=100)
    store_code: str = Field(..., min_length=1, max_length=50)
    timestamp: datetime
    event_key: Optional[str] = Field(None, min_length=8, max_length=80)
    camera_id: Optional[str] = Field(None, max_length=100)
    zone_id: Optional[str] = Field(None, max_length=100)
    zone_name: Optional[str] = Field(None, max_length=200)
    zone_type: Optional[str] = Field(None, max_length=50)
    confidence: Optional[float] = Field(None, ge=0, le=1)
    dwell_seconds: Optional[float] = Field(None, ge=0, le=86400)
    queue_wait_seconds: Optional[float] = Field(None, ge=0, le=86400)
    queue_abandoned: Optional[bool] = None
    is_staff: bool = False
    metadata_json: Optional[dict] = None

    @field_validator("timestamp")
    @classmethod
    def _aware(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("timestamp must include a time zone offset, e.g. 2026-03-08T10:00:00+05:30 or ...Z")
        return v.astimezone(UTC).replace(tzinfo=None)


class EventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    store_id: uuid.UUID
    event_type: str
    customer_id: str
    camera_id: Optional[str] = None
    zone_id: Optional[str] = None
    zone_name: Optional[str] = None
    zone_type: Optional[str] = None
    timestamp: datetime
    source: str
    event_key: Optional[str] = None
    job_id: Optional[uuid.UUID] = None
    track_id: Optional[int] = None
    video_offset_seconds: Optional[float] = None
    confidence: Optional[float] = None
    bbox_x: Optional[float] = None
    bbox_y: Optional[float] = None
    bbox_w: Optional[float] = None
    bbox_h: Optional[float] = None
    dwell_seconds: Optional[float] = None
    queue_wait_seconds: Optional[float] = None
    queue_abandoned: Optional[bool] = None
    metadata_json: Optional[dict] = None
    created_at: datetime


class EventPage(BaseModel):
    total: int
    limit: int
    offset: int
    items: List[EventResponse]


class IngestResult(BaseModel):
    received: int
    inserted: int
    duplicates: int
    errors: List[str] = Field(default_factory=list)
