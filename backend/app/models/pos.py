"""POS Transaction model."""

from __future__ import annotations

import uuid
from datetime import date, datetime, time
from typing import Optional

from sqlalchemy import Date, DateTime, Float, Index, Integer, String, Time, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, utcnow


class POSTransaction(Base):
    """One POS line item.

    ``store_id`` holds the POS system's own store code (e.g. "ST1076"), which
    maps to ``Store.pos_store_code``. ``order_date``/``order_time`` are in the
    store's local time zone, as exported by the POS; ``ordered_at_utc`` is the
    same instant converted to naive UTC at import time.
    """

    __tablename__ = "pos_transactions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    order_id: Mapped[int] = mapped_column(Integer, index=True)
    store_id: Mapped[str] = mapped_column(String(50), index=True)
    order_date: Mapped[date] = mapped_column(Date)
    order_time: Mapped[time] = mapped_column(Time)
    ordered_at_utc: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
    product_id: Mapped[str] = mapped_column(String(50))
    brand_name: Mapped[str] = mapped_column(String(200))
    total_amount: Mapped[float] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String(20), default="api", server_default="api")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    __table_args__ = (
        Index("ix_pos_store_date", "store_id", "order_date"),
        UniqueConstraint("store_id", "order_id", "product_id", name="uq_pos_line"),
    )

    def __repr__(self) -> str:
        return f"<POS Order #{self.order_id}: {self.brand_name} {self.total_amount}>"
