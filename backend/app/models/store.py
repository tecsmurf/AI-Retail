"""Store, Camera, and Zone models."""

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
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class Store(Base):
    """Physical retail store."""

    __tablename__ = "stores"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    store_code: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    city: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    layout_image_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    layout_width: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    layout_height: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    cameras: Mapped[List["Camera"]] = relationship(back_populates="store", cascade="all, delete-orphan")
    zones: Mapped[List["Zone"]] = relationship(back_populates="store", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Store {self.store_code}: {self.name}>"


class Camera(Base):
    """CCTV camera in a store."""

    __tablename__ = "cameras"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    store_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stores.id", ondelete="CASCADE")
    )
    camera_code: Mapped[str] = mapped_column(String(50), index=True)
    name: Mapped[str] = mapped_column(String(200))
    camera_type: Mapped[str] = mapped_column(
        String(50)  # 'entrance', 'zone', 'billing'
    )
    stream_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    resolution_width: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    resolution_height: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    fps: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    position_on_layout: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True  # {"x": 100, "y": 200}
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )

    # Relationships
    store: Mapped["Store"] = relationship(back_populates="cameras")

    def __repr__(self) -> str:
        return f"<Camera {self.camera_code}: {self.name}>"


class Zone(Base):
    """Business zone within a store (shelf, display, billing, entrance)."""

    __tablename__ = "zones"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    store_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stores.id", ondelete="CASCADE")
    )
    zone_code: Mapped[str] = mapped_column(String(100), index=True)
    name: Mapped[str] = mapped_column(String(200))
    zone_type: Mapped[str] = mapped_column(
        String(50)  # 'SHELF', 'DISPLAY', 'BILLING', 'ENTRANCE', 'EXIT'
    )
    is_revenue_zone: Mapped[bool] = mapped_column(Boolean, default=False)
    polygon_points: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True  # [[x1,y1], [x2,y2], ...]
    )
    camera_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cameras.id"), nullable=True
    )
    color: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True  # hex color for heatmap
    )
    display_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )

    # Relationships
    store: Mapped["Store"] = relationship(back_populates="zones")

    def __repr__(self) -> str:
        return f"<Zone {self.zone_code}: {self.name}>"
