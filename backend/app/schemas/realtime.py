"""Real-time update schemas for WebSocket communication."""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class LiveStoreStatus(BaseModel):
    """Real-time store status pushed via WebSocket."""
    store_id: str
    store_name: str
    active_customers: int = 0
    zone_occupancy: Dict[str, int] = Field(default_factory=dict)
    current_queue_length: int = 0
    avg_queue_wait: float = 0.0
    recent_events: List[dict] = Field(default_factory=list)
    alerts: List[dict] = Field(default_factory=list)
    timestamp: datetime


class RealtimeUpdate(BaseModel):
    """Generic real-time update payload."""
    type: str  # "event", "alert", "status", "analytics"
    store_id: Optional[str] = None
    data: dict = Field(default_factory=dict)
    timestamp: datetime
