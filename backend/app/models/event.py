"""Event, CustomerJourney, and JourneyEvent models."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import List, Optional

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
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class Event(Base):
    """Business event generated from CV detections."""

    __tablename__ = "events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    store_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stores.id", ondelete="CASCADE"), index=True
    )
    event_type: Mapped[str] = mapped_column(
        String(50), index=True
        # ENTRY, EXIT, ZONE_ENTER, ZONE_EXIT, DWELL_TIME,
        # CHECKOUT, QUEUE_ENTER, QUEUE_EXIT,
        # PRODUCT_INTERACTION, PRODUCT_PICKUP, PRODUCT_RETURN
    )
    customer_id: Mapped[str] = mapped_column(String(100), index=True)
    camera_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    zone_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    zone_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    zone_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, index=True)

    # Detection metadata
    confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    bbox_x: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    bbox_y: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    bbox_w: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    bbox_h: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    hotspot_x: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    hotspot_y: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Demographics
    gender: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    age: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    age_bucket: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    is_staff: Mapped[bool] = mapped_column(Boolean, default=False)

    # Queue-specific
    queue_wait_seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    queue_position: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    queue_abandoned: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)

    # Group info
    group_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    group_size: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Dwell time (for DWELL_TIME events)
    dwell_seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Extra metadata
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )

    __table_args__ = (
        Index("ix_events_store_time", "store_id", "timestamp"),
        Index("ix_events_store_type", "store_id", "event_type"),
        Index("ix_events_customer", "store_id", "customer_id", "timestamp"),
    )

    def __repr__(self) -> str:
        return f"<Event {self.event_type} customer={self.customer_id}>"


class CustomerJourney(Base):
    """Reconstructed customer journey through a store."""

    __tablename__ = "customer_journeys"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    store_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stores.id", ondelete="CASCADE"), index=True
    )
    customer_id: Mapped[str] = mapped_column(String(100), index=True)
    entry_time: Mapped[datetime] = mapped_column(DateTime)
    exit_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    duration_seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    zones_visited: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True  # ["Zone A", "Zone B", "Billing"]
    )
    zone_count: Mapped[int] = mapped_column(Integer, default=0)
    total_dwell_seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    made_purchase: Mapped[bool] = mapped_column(Boolean, default=False)
    visited_billing: Mapped[bool] = mapped_column(Boolean, default=False)
    journey_type: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True  # 'conversion', 'browse', 'bounce', 'abandonment'
    )

    # Demographics
    gender: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    age_bucket: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    # POS correlation
    pos_transaction_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    purchase_amount: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )

    # Relationships
    journey_events: Mapped[List["JourneyEvent"]] = relationship(
        back_populates="journey", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_journeys_store_time", "store_id", "entry_time"),
    )

    def __repr__(self) -> str:
        return f"<Journey {self.customer_id}: {self.journey_type}>"


class JourneyEvent(Base):
    """Individual step in a customer journey."""

    __tablename__ = "journey_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    journey_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customer_journeys.id", ondelete="CASCADE")
    )
    sequence: Mapped[int] = mapped_column(Integer)
    event_type: Mapped[str] = mapped_column(String(50))
    zone_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime)
    dwell_seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Relationships
    journey: Mapped["CustomerJourney"] = relationship(back_populates="journey_events")

    def __repr__(self) -> str:
        return f"<JourneyEvent #{self.sequence}: {self.event_type}>"
