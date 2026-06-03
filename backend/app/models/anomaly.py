"""Anomaly and Alert models."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    String,
    Text,
    Float,
    Integer,
    Boolean,
    DateTime,
    ForeignKey,
    JSON,
    Index,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class Anomaly(Base):
    """Detected anomaly in store operations."""

    __tablename__ = "anomalies"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    store_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stores.id", ondelete="CASCADE"), index=True
    )
    anomaly_type: Mapped[str] = mapped_column(
        String(50), index=True
        # LONG_QUEUE, ABNORMAL_DWELL, TRAFFIC_DROP,
        # EMPTY_STORE, UNUSUAL_MOVEMENT
    )
    severity: Mapped[str] = mapped_column(
        String(20)  # 'low', 'medium', 'high', 'critical'
    )
    zone_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    description: Mapped[str] = mapped_column(Text)
    metric_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    threshold_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    detected_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    is_resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )

    def __repr__(self) -> str:
        return f"<Anomaly {self.anomaly_type}: {self.severity}>"


class Alert(Base):
    """Real-time alert generated from anomaly detection."""

    __tablename__ = "alerts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    anomaly_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("anomalies.id"), nullable=True
    )
    store_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stores.id", ondelete="CASCADE"), index=True
    )
    alert_type: Mapped[str] = mapped_column(String(50))
    title: Mapped[str] = mapped_column(String(300))
    message: Mapped[str] = mapped_column(Text)
    severity: Mapped[str] = mapped_column(String(20))
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, index=True
    )

    def __repr__(self) -> str:
        return f"<Alert {self.alert_type}: {self.title}>"
