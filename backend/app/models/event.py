"""Event, CustomerJourney, and JourneyEvent models."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, utcnow

# Where a record came from. Analytics include only REAL_SOURCES by default.
EVENT_SOURCES = ("cv", "api", "sample", "demo", "legacy_cv")
REAL_SOURCES = ("cv", "api")

EVENT_TYPES = (
    "ENTRY",
    "EXIT",
    "ZONE_ENTER",
    "ZONE_EXIT",
    "QUEUE_ENTER",
    "QUEUE_EXIT",
    "QUEUE_COMPLETED",
    "QUEUE_ABANDONED",
    # Legacy types kept readable for imported data.
    "DWELL_TIME",
    "CHECKOUT",
)


class Event(Base):
    """Business event (from the CV pipeline, the ingestion API, or imports).

    ``customer_id`` is an anonymous, temporary track identifier scoped to one
    processed video and camera. It is never linked to a person's identity.
    """

    __tablename__ = "events"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    store_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("stores.id", ondelete="CASCADE"), index=True)
    event_type: Mapped[str] = mapped_column(String(50), index=True)
    customer_id: Mapped[str] = mapped_column(String(100), index=True)
    camera_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    zone_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    zone_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    zone_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, index=True)  # naive UTC

    # Provenance / idempotency
    source: Mapped[str] = mapped_column(String(20), default="api", server_default="api", index=True)
    event_key: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    job_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("processing_jobs.id", ondelete="CASCADE"), nullable=True, index=True
    )
    track_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    video_offset_seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Detection metadata (normalized 0..1 frame coordinates for CV events)
    confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    bbox_x: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    bbox_y: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    bbox_w: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    bbox_h: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    hotspot_x: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    hotspot_y: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Legacy demographic columns. The CV pipeline never fills these and the
    # API does not expose them; they are kept only so imported data survives.
    gender: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    age: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    age_bucket: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    is_staff: Mapped[bool] = mapped_column(Boolean, default=False)

    # Queue-specific
    queue_wait_seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    queue_position: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    queue_abandoned: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)

    group_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    group_size: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    dwell_seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    __table_args__ = (
        Index("ix_events_store_time", "store_id", "timestamp"),
        Index("ix_events_store_type", "store_id", "event_type"),
        Index("ix_events_customer", "store_id", "customer_id", "timestamp"),
        UniqueConstraint("store_id", "event_key", name="uq_events_store_event_key"),
    )

    def __repr__(self) -> str:
        return f"<Event {self.event_type} customer={self.customer_id}>"


class CustomerJourney(Base):
    """Journey of one anonymous track as seen by one camera.

    Tracks are not linked across cameras (no re-identification), so a journey
    describes what a single camera observed.
    """

    __tablename__ = "customer_journeys"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    store_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("stores.id", ondelete="CASCADE"), index=True)
    customer_id: Mapped[str] = mapped_column(String(100), index=True)
    job_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("processing_jobs.id", ondelete="CASCADE"), nullable=True, index=True
    )
    camera_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    source: Mapped[str] = mapped_column(String(20), default="cv", server_default="cv", index=True)
    entry_time: Mapped[datetime] = mapped_column(DateTime)
    exit_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    duration_seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    zones_visited: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    zone_count: Mapped[int] = mapped_column(Integer, default=0)
    total_dwell_seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    # True only when a POS transaction was matched to this journey.
    made_purchase: Mapped[bool] = mapped_column(Boolean, default=False)
    visited_billing: Mapped[bool] = mapped_column(Boolean, default=False)
    # observed_entry/observed_exit: whether ENTRY/EXIT were actually observed.
    observed_entry: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    observed_exit: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    journey_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    gender: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)  # legacy
    age_bucket: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # legacy

    pos_transaction_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    purchase_amount: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    journey_events: Mapped[List[JourneyEvent]] = relationship(
        back_populates="journey", cascade="all, delete-orphan", order_by="JourneyEvent.sequence"
    )

    __table_args__ = (Index("ix_journeys_store_time", "store_id", "entry_time"),)

    def __repr__(self) -> str:
        return f"<Journey {self.customer_id}: {self.journey_type}>"


class JourneyEvent(Base):
    """Individual step in a customer journey."""

    __tablename__ = "journey_events"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    journey_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("customer_journeys.id", ondelete="CASCADE"), index=True
    )
    sequence: Mapped[int] = mapped_column(Integer)
    event_type: Mapped[str] = mapped_column(String(50))
    zone_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime)
    dwell_seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    journey: Mapped[CustomerJourney] = relationship(back_populates="journey_events")

    def __repr__(self) -> str:
        return f"<JourneyEvent #{self.sequence}: {self.event_type}>"
