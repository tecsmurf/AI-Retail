"""Store-related Pydantic schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


# ── Store ────────────────────────────────────────────────────────

class StoreCreate(BaseModel):
    """Schema for creating a new store."""
    store_code: str = Field(..., max_length=50, examples=["store_1076"])
    name: str = Field(..., max_length=200, examples=["Purplle Mumbai Store 1"])
    address: Optional[str] = None
    city: Optional[str] = None
    layout_image_url: Optional[str] = None
    layout_width: Optional[int] = None
    layout_height: Optional[int] = None


class StoreResponse(BaseModel):
    """Store response schema."""
    id: uuid.UUID
    store_code: str
    name: str
    address: Optional[str] = None
    city: Optional[str] = None
    layout_image_url: Optional[str] = None
    layout_width: Optional[int] = None
    layout_height: Optional[int] = None
    is_active: bool
    camera_count: int = 0
    zone_count: int = 0
    created_at: datetime

    model_config = {"from_attributes": True}


class StoreOverview(BaseModel):
    """Store overview with key metrics."""
    store: StoreResponse
    total_visitors_today: int = 0
    active_visitors: int = 0
    conversion_rate: float = 0.0
    avg_dwell_time: float = 0.0
    revenue_today: float = 0.0
    peak_hour: Optional[str] = None
    active_alerts: int = 0
    zone_occupancy: dict = Field(default_factory=dict)


# ── Camera ───────────────────────────────────────────────────────

class CameraResponse(BaseModel):
    """Camera response schema."""
    id: uuid.UUID
    camera_code: str
    name: str
    camera_type: str
    stream_url: Optional[str] = None
    resolution_width: Optional[int] = None
    resolution_height: Optional[int] = None
    fps: Optional[float] = None
    is_active: bool
    position_on_layout: Optional[dict] = None

    model_config = {"from_attributes": True}


# ── Zone ─────────────────────────────────────────────────────────

class ZoneResponse(BaseModel):
    """Zone response schema."""
    id: uuid.UUID
    zone_code: str
    name: str
    zone_type: str
    is_revenue_zone: bool
    polygon_points: Optional[dict] = None
    color: Optional[str] = None
    display_order: int

    model_config = {"from_attributes": True}


class ZoneAnalytics(BaseModel):
    """Zone-level analytics."""
    zone_name: str
    zone_type: str
    total_visits: int = 0
    unique_visitors: int = 0
    avg_dwell_seconds: float = 0.0
    max_dwell_seconds: float = 0.0
    conversion_rate: float = 0.0
    revenue_contribution: float = 0.0
    popularity_rank: int = 0
    current_occupancy: int = 0
    hourly_visits: List[HourlyZoneVisits] = Field(default_factory=list)


class HourlyZoneVisits(BaseModel):
    """Hourly visit data for a zone."""
    hour: int
    visits: int
    avg_dwell: float
