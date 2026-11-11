"""In-store edge boxes: a small computer on the store's network that reads
the CCTV recorder's live streams, runs the same CV pipeline on site and sends
only anonymous events and counts to the cloud. No video leaves the store.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, utcnow

EDGE_PENDING = "pending"   # created in the dashboard, waiting for the box to pair
EDGE_ACTIVE = "active"
EDGE_REVOKED = "revoked"


class EdgeDevice(Base):
    __tablename__ = "edge_devices"
    __table_args__ = (UniqueConstraint("token_hash", name="uq_edge_devices_token_hash"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    store_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("stores.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(20), default=EDGE_PENDING)
    # Only hashes are stored: the pairing code is shown once in the dashboard,
    # the token is returned once to the box.
    pairing_code_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    pairing_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    token_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    hostname: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    agent_version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    last_seen_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_ip: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    # {camera_id: {status, message, fps, last_frame_at, width, height}} as last reported by the box.
    camera_status: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    stats: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    # Camera ids the dashboard asked a fresh still image for.
    snapshot_requests: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    events_received: Mapped[int] = mapped_column(Integer, default=0)
    last_event_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    paired_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class EdgeCoverage(Base):
    """Seconds of live stream analysed per camera and UTC hour, so the
    dashboard can tell "no visitors" from "the camera was not being watched"."""

    __tablename__ = "edge_coverage"

    camera_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("cameras.id", ondelete="CASCADE"), primary_key=True)
    hour: Mapped[datetime] = mapped_column(DateTime, primary_key=True)
    store_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("stores.id", ondelete="CASCADE"), index=True)
    seconds: Mapped[float] = mapped_column(Float, default=0.0)
