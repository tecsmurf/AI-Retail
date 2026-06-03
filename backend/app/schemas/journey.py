"""Journey-related Pydantic schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class JourneyStep(BaseModel):
    """Single step in a customer journey."""
    sequence: int
    event_type: str
    zone_name: Optional[str] = None
    timestamp: datetime
    dwell_seconds: Optional[float] = None


class JourneyResponse(BaseModel):
    """Customer journey response."""
    id: uuid.UUID
    store_id: uuid.UUID
    customer_id: str
    entry_time: datetime
    exit_time: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    zones_visited: Optional[list] = None
    zone_count: int = 0
    total_dwell_seconds: Optional[float] = None
    made_purchase: bool = False
    visited_billing: bool = False
    journey_type: Optional[str] = None
    gender: Optional[str] = None
    age_bucket: Optional[str] = None
    purchase_amount: Optional[float] = None
    steps: List[JourneyStep] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class TopPath(BaseModel):
    """Most common customer path through the store."""
    path: List[str]  # ["ENTRY", "Loreal", "Mars", "Billing", "EXIT"]
    count: int
    avg_duration_seconds: float
    conversion_rate: float


class JourneyAnalytics(BaseModel):
    """Journey analytics summary."""
    total_journeys: int = 0
    avg_journey_duration: float = 0.0
    avg_zones_visited: float = 0.0
    conversion_journeys: int = 0
    abandonment_journeys: int = 0
    browse_journeys: int = 0
    bounce_journeys: int = 0
    top_paths: List[TopPath] = Field(default_factory=list)
    conversion_rate: float = 0.0
