"""POS Transaction model."""

from __future__ import annotations

import uuid
from datetime import datetime, date, time
from typing import Optional

from sqlalchemy import (
    String,
    Float,
    Integer,
    Date,
    Time,
    DateTime,
    ForeignKey,
    Index,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class POSTransaction(Base):
    """Point-of-sale transaction record."""

    __tablename__ = "pos_transactions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    order_id: Mapped[int] = mapped_column(Integer, index=True)
    store_id: Mapped[str] = mapped_column(String(50), index=True)
    order_date: Mapped[date] = mapped_column(Date)
    order_time: Mapped[time] = mapped_column(Time)
    product_id: Mapped[str] = mapped_column(String(50))
    brand_name: Mapped[str] = mapped_column(String(200))
    total_amount: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )

    __table_args__ = (
        Index("ix_pos_store_date", "store_id", "order_date"),
    )

    def __repr__(self) -> str:
        return f"<POS Order #{self.order_id}: {self.brand_name} ₹{self.total_amount}>"
