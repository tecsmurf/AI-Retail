"""Anomaly and Alert models."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, utcnow


class Anomaly(Base):
    """Rule-based anomaly detected from persisted metrics.

    ``dedupe_key`` makes re-running detection over the same window idempotent.
    """

    __tablename__ = "anomalies"
    __table_args__ = (UniqueConstraint("store_id", "dedupe_key", name="uq_anomalies_dedupe"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    store_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("stores.id", ondelete="CASCADE"), index=True)
    anomaly_type: Mapped[str] = mapped_column(String(50), index=True)
    severity: Mapped[str] = mapped_column(String(20))
    zone_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    description: Mapped[str] = mapped_column(Text)
    metric_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    threshold_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    detected_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    is_resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    dedupe_key: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    def __repr__(self) -> str:
        return f"<Anomaly {self.anomaly_type}: {self.severity}>"


class Alert(Base):
    """User-facing alert (from an anomaly or a failed processing job)."""

    __tablename__ = "alerts"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    anomaly_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("anomalies.id"), nullable=True
    )
    store_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("stores.id", ondelete="CASCADE"), index=True)
    alert_type: Mapped[str] = mapped_column(String(50))
    title: Mapped[str] = mapped_column(String(300))
    message: Mapped[str] = mapped_column(Text)
    severity: Mapped[str] = mapped_column(String(20))
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)

    def __repr__(self) -> str:
        return f"<Alert {self.alert_type}: {self.title}>"
