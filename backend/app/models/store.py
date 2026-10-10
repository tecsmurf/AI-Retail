"""Store, Camera, and Zone models."""

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
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, utcnow

ZONE_TYPES = ("ENTRANCE", "SHELF", "DISPLAY", "QUEUE", "BILLING", "EXIT", "OTHER")
CAMERA_TYPES = ("entrance", "zone", "billing", "other")


class Store(Base):
    """Physical retail store."""

    __tablename__ = "stores"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    store_code: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    city: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    # IANA time zone used for day boundaries and hourly charts.
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Kolkata", server_default="Asia/Kolkata")
    # Identifier used by the store's POS export (e.g. "ST1076").
    pos_store_code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    layout_image_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    layout_width: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    layout_height: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    cameras: Mapped[List[Camera]] = relationship(back_populates="store", cascade="all, delete-orphan")
    zones: Mapped[List[Zone]] = relationship(back_populates="store", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Store {self.store_code}: {self.name}>"


class Camera(Base):
    """CCTV camera in a store.

    ``entry_line`` (entrance cameras) is a virtual line in normalized frame
    coordinates: ``{"p1": [x, y], "p2": [x, y], "inside": "left"|"right"}``.
    "left"/"right" is relative to walking from p1 to p2 in image coordinates.
    """

    __tablename__ = "cameras"
    __table_args__ = (UniqueConstraint("store_id", "camera_code", name="uq_cameras_store_code"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    store_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("stores.id", ondelete="CASCADE"), index=True)
    camera_code: Mapped[str] = mapped_column(String(50), index=True)
    name: Mapped[str] = mapped_column(String(200))
    camera_type: Mapped[str] = mapped_column(String(50))  # entrance | zone | billing | other
    stream_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    resolution_width: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    resolution_height: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    fps: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    position_on_layout: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    entry_line: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    # Storage key of a JPEG frame used as the backdrop of the zone editor.
    reference_frame_key: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    reference_frame_width: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    reference_frame_height: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # Incremented whenever zones or the entry line change; jobs record it.
    config_version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    store: Mapped[Store] = relationship(back_populates="cameras")
    zones: Mapped[List[Zone]] = relationship(back_populates="camera", foreign_keys="Zone.camera_id")

    def __repr__(self) -> str:
        return f"<Camera {self.camera_code}: {self.name}>"


class Zone(Base):
    """Business zone within a store.

    ``polygon_points`` is a list of ``[x, y]`` pairs in *normalized* frame
    coordinates (0..1, origin top-left) of the zone's camera, so a polygon stays
    aligned regardless of the resolution a video is recorded or displayed at.
    Zones without a camera or polygon are layout labels only and never assigned
    by the CV pipeline.
    """

    __tablename__ = "zones"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    store_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("stores.id", ondelete="CASCADE"), index=True)
    zone_code: Mapped[str] = mapped_column(String(100), index=True)
    name: Mapped[str] = mapped_column(String(200))
    zone_type: Mapped[str] = mapped_column(String(50))
    is_revenue_zone: Mapped[bool] = mapped_column(Boolean, default=False)
    polygon_points: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    camera_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("cameras.id"), nullable=True, index=True
    )
    # Higher priority wins where polygons overlap; ties go to the smaller area.
    priority: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    color: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    display_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, onupdate=utcnow)

    store: Mapped[Store] = relationship(back_populates="zones")
    camera: Mapped[Optional[Camera]] = relationship(back_populates="zones", foreign_keys=[camera_id])

    def __repr__(self) -> str:
        return f"<Zone {self.zone_code}: {self.name}>"
