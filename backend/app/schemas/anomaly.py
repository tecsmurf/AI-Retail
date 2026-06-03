"""Anomaly and Alert Pydantic schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class AnomalyResponse(BaseModel):
    """Anomaly response schema."""
    id: uuid.UUID
    store_id: uuid.UUID
    anomaly_type: str
    severity: str
    zone_name: Optional[str] = None
    description: str
    metric_value: Optional[float] = None
    threshold_value: Optional[float] = None
    detected_at: datetime
    resolved_at: Optional[datetime] = None
    is_resolved: bool
    metadata_json: Optional[dict] = None

    model_config = {"from_attributes": True}


class AlertResponse(BaseModel):
    """Alert response schema."""
    id: uuid.UUID
    anomaly_id: Optional[uuid.UUID] = None
    store_id: uuid.UUID
    alert_type: str
    title: str
    message: str
    severity: str
    is_read: bool
    created_at: datetime

    model_config = {"from_attributes": True}
