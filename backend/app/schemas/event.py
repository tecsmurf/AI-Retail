"""Event-related Pydantic schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class EventCreate(BaseModel):
    """Schema for creating a new event."""
    event_type: str = Field(
        ...,
        examples=["ZONE_ENTER"],
        description="Event type: ENTRY, EXIT, ZONE_ENTER, ZONE_EXIT, DWELL_TIME, CHECKOUT, QUEUE_ENTER, QUEUE_EXIT",
    )
    customer_id: str = Field(..., examples=["CUST_001"])
    store_code: str = Field(..., examples=["store_1076"])
    camera_id: Optional[str] = None
    zone_id: Optional[str] = None
    zone_name: Optional[str] = None
    zone_type: Optional[str] = None
    timestamp: datetime
    confidence: Optional[float] = None
    bbox_x: Optional[float] = None
    bbox_y: Optional[float] = None
    bbox_w: Optional[float] = None
    bbox_h: Optional[float] = None
    hotspot_x: Optional[float] = None
    hotspot_y: Optional[float] = None
    gender: Optional[str] = None
    age: Optional[int] = None
    age_bucket: Optional[str] = None
    is_staff: bool = False
    queue_wait_seconds: Optional[float] = None
    queue_position: Optional[int] = None
    queue_abandoned: Optional[bool] = None
    group_id: Optional[str] = None
    group_size: Optional[int] = None
    dwell_seconds: Optional[float] = None
    metadata_json: Optional[dict] = None


class EventResponse(BaseModel):
    """Event response schema."""
    id: uuid.UUID
    store_id: uuid.UUID
    event_type: str
    customer_id: str
    camera_id: Optional[str] = None
    zone_id: Optional[str] = None
    zone_name: Optional[str] = None
    zone_type: Optional[str] = None
    timestamp: datetime
    confidence: Optional[float] = None
    gender: Optional[str] = None
    age: Optional[int] = None
    age_bucket: Optional[str] = None
    is_staff: bool = False
    dwell_seconds: Optional[float] = None
    queue_wait_seconds: Optional[float] = None
    queue_abandoned: Optional[bool] = None
    group_id: Optional[str] = None
    group_size: Optional[int] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class EventFilter(BaseModel):
    """Filter parameters for querying events."""
    store_id: Optional[uuid.UUID] = None
    event_type: Optional[str] = None
    customer_id: Optional[str] = None
    zone_name: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    is_staff: Optional[bool] = None
    limit: int = Field(default=100, le=1000)
    offset: int = Field(default=0, ge=0)
