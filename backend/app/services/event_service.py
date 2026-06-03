"""Event service — ingestion, querying, and event-to-journey processing."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import List, Optional, Dict

from sqlalchemy import select, func, and_, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.event import Event, CustomerJourney, JourneyEvent
from app.models.store import Store
from app.schemas.event import EventCreate, EventFilter


class EventService:
    """Service for event ingestion and querying."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ── Ingestion ────────────────────────────────────────────────

    async def ingest_event(self, data: EventCreate) -> Event:
        """Ingest a single business event."""
        # Resolve store ID from store_code
        store = await self._get_store_by_code(data.store_code)
        if not store:
            raise ValueError(f"Store not found: {data.store_code}")

        event = Event(
            store_id=store.id,
            event_type=data.event_type.upper(),
            customer_id=data.customer_id,
            camera_id=data.camera_id,
            zone_id=data.zone_id,
            zone_name=data.zone_name,
            zone_type=data.zone_type,
            timestamp=data.timestamp,
            confidence=data.confidence,
            bbox_x=data.bbox_x,
            bbox_y=data.bbox_y,
            bbox_w=data.bbox_w,
            bbox_h=data.bbox_h,
            hotspot_x=data.hotspot_x,
            hotspot_y=data.hotspot_y,
            gender=data.gender,
            age=data.age,
            age_bucket=data.age_bucket,
            is_staff=data.is_staff,
            queue_wait_seconds=data.queue_wait_seconds,
            queue_position=data.queue_position,
            queue_abandoned=data.queue_abandoned,
            group_id=data.group_id,
            group_size=data.group_size,
            dwell_seconds=data.dwell_seconds,
            metadata_json=data.metadata_json,
        )
        self.db.add(event)
        await self.db.flush()
        return event

    async def ingest_batch(self, events: List[EventCreate]) -> int:
        """Ingest a batch of events. Returns count of ingested events."""
        count = 0
        for event_data in events:
            try:
                await self.ingest_event(event_data)
                count += 1
            except ValueError:
                continue
        return count

    # ── Querying ─────────────────────────────────────────────────

    async def get_events(self, filters: EventFilter) -> List[Event]:
        """Query events with filters."""
        query = select(Event)

        if filters.store_id:
            query = query.where(Event.store_id == filters.store_id)
        if filters.event_type:
            query = query.where(Event.event_type == filters.event_type.upper())
        if filters.customer_id:
            query = query.where(Event.customer_id == filters.customer_id)
        if filters.zone_name:
            query = query.where(Event.zone_name == filters.zone_name)
        if filters.start_time:
            query = query.where(Event.timestamp >= filters.start_time)
        if filters.end_time:
            query = query.where(Event.timestamp <= filters.end_time)
        if filters.is_staff is not None:
            query = query.where(Event.is_staff == filters.is_staff)

        query = query.order_by(Event.timestamp.desc())
        query = query.limit(filters.limit).offset(filters.offset)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_events_for_customer(
        self, store_id: uuid.UUID, customer_id: str
    ) -> List[Event]:
        """Get all events for a specific customer in a store."""
        result = await self.db.execute(
            select(Event)
            .where(
                Event.store_id == store_id,
                Event.customer_id == customer_id,
            )
            .order_by(Event.timestamp)
        )
        return list(result.scalars().all())

    async def get_event_count(
        self,
        store_id: uuid.UUID,
        event_type: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> int:
        """Count events matching criteria."""
        query = select(func.count(Event.id)).where(Event.store_id == store_id)
        if event_type:
            query = query.where(Event.event_type == event_type)
        if start_time:
            query = query.where(Event.timestamp >= start_time)
        if end_time:
            query = query.where(Event.timestamp <= end_time)

        result = await self.db.execute(query)
        return result.scalar() or 0

    async def get_unique_customers(
        self,
        store_id: uuid.UUID,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> int:
        """Count unique customers in a time range."""
        query = select(func.count(func.distinct(Event.customer_id))).where(
            Event.store_id == store_id,
            Event.event_type == "ENTRY",
            Event.is_staff.is_(False),
        )
        if start_time:
            query = query.where(Event.timestamp >= start_time)
        if end_time:
            query = query.where(Event.timestamp <= end_time)

        result = await self.db.execute(query)
        return result.scalar() or 0

    async def get_hourly_footfall(
        self, store_id: uuid.UUID, date: datetime
    ) -> List[Dict]:
        """Get hourly footfall for a specific date."""
        start = date.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)

        result = await self.db.execute(
            select(
                func.extract("hour", Event.timestamp).label("hour"),
                func.count(func.distinct(Event.customer_id)).label("visitors"),
            )
            .where(
                Event.store_id == store_id,
                Event.event_type == "ENTRY",
                Event.is_staff.is_(False),
                Event.timestamp >= start,
                Event.timestamp < end,
            )
            .group_by(func.extract("hour", Event.timestamp))
            .order_by(func.extract("hour", Event.timestamp))
        )

        hour_labels = [
            "12 AM", "1 AM", "2 AM", "3 AM", "4 AM", "5 AM",
            "6 AM", "7 AM", "8 AM", "9 AM", "10 AM", "11 AM",
            "12 PM", "1 PM", "2 PM", "3 PM", "4 PM", "5 PM",
            "6 PM", "7 PM", "8 PM", "9 PM", "10 PM", "11 PM",
        ]

        hourly_data = {int(row.hour): row.visitors for row in result}
        return [
            {"hour": h, "visitors": hourly_data.get(h, 0), "label": hour_labels[h]}
            for h in range(24)
        ]

    # ── Helpers ──────────────────────────────────────────────────

    async def _get_store_by_code(self, store_code: str) -> Optional[Store]:
        """Look up store by code."""
        result = await self.db.execute(
            select(Store).where(Store.store_code == store_code)
        )
        return result.scalar_one_or_none()
