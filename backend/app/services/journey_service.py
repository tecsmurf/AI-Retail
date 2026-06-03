"""Journey service — reconstruct and analyze customer journeys."""

from __future__ import annotations

import uuid
from collections import Counter
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Tuple

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.event import Event, CustomerJourney, JourneyEvent


class JourneyService:
    """Service for customer journey reconstruction and analysis."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ── Journey Reconstruction ───────────────────────────────────

    async def reconstruct_journeys(
        self,
        store_id: uuid.UUID,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> int:
        """
        Reconstruct customer journeys from raw events.
        Groups events by customer_id, orders by timestamp,
        and creates journey records.
        Returns count of journeys created.
        """
        # Get all entry events in the time range
        query = (
            select(Event.customer_id)
            .where(
                Event.store_id == store_id,
                Event.event_type == "ENTRY",
                Event.is_staff.is_(False),
            )
            .distinct()
        )
        if start_time:
            query = query.where(Event.timestamp >= start_time)
        if end_time:
            query = query.where(Event.timestamp <= end_time)

        result = await self.db.execute(query)
        customer_ids = [row[0] for row in result.all()]

        count = 0
        for customer_id in customer_ids:
            journey = await self._build_journey(store_id, customer_id)
            if journey:
                self.db.add(journey)
                count += 1

        await self.db.flush()
        return count

    async def _build_journey(
        self, store_id: uuid.UUID, customer_id: str
    ) -> Optional[CustomerJourney]:
        """Build a single customer journey from events."""
        result = await self.db.execute(
            select(Event)
            .where(
                Event.store_id == store_id,
                Event.customer_id == customer_id,
            )
            .order_by(Event.timestamp)
        )
        events = list(result.scalars().all())

        if not events:
            return None

        # Find entry and exit
        entry_event = next(
            (e for e in events if e.event_type == "ENTRY"), events[0]
        )
        exit_event = next(
            (e for e in events if e.event_type == "EXIT"), None
        )

        # Collect zones visited
        zones = []
        for e in events:
            if e.event_type in ("ZONE_ENTER", "ZONE_ENTERED") and e.zone_name:
                if e.zone_name not in zones:
                    zones.append(e.zone_name)

        # Calculate total dwell
        total_dwell = sum(
            e.dwell_seconds or 0
            for e in events
            if e.event_type == "DWELL_TIME"
        )

        # Check billing
        visited_billing = any(
            e.zone_type == "BILLING" or e.event_type in ("CHECKOUT", "QUEUE_COMPLETED")
            for e in events
        )

        # Determine journey type
        duration = None
        if exit_event:
            duration = (exit_event.timestamp - entry_event.timestamp).total_seconds()

        journey_type = self._classify_journey(
            zones_count=len(zones),
            visited_billing=visited_billing,
            duration=duration,
        )

        journey = CustomerJourney(
            store_id=store_id,
            customer_id=customer_id,
            entry_time=entry_event.timestamp,
            exit_time=exit_event.timestamp if exit_event else None,
            duration_seconds=duration,
            zones_visited=zones,
            zone_count=len(zones),
            total_dwell_seconds=total_dwell if total_dwell > 0 else None,
            made_purchase=visited_billing,  # approximation
            visited_billing=visited_billing,
            journey_type=journey_type,
            gender=entry_event.gender,
            age_bucket=entry_event.age_bucket,
        )

        # Create journey events (steps)
        for seq, event in enumerate(events, 1):
            step = JourneyEvent(
                sequence=seq,
                event_type=event.event_type,
                zone_name=event.zone_name,
                timestamp=event.timestamp,
                dwell_seconds=event.dwell_seconds,
            )
            journey.journey_events.append(step)

        return journey

    def _classify_journey(
        self,
        zones_count: int,
        visited_billing: bool,
        duration: Optional[float],
    ) -> str:
        """Classify a journey type."""
        if visited_billing:
            return "conversion"
        if zones_count == 0:
            return "bounce"
        if duration and duration < 60:
            return "bounce"
        return "browse"

    # ── Querying ─────────────────────────────────────────────────

    async def get_journeys(
        self,
        store_id: uuid.UUID,
        journey_type: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[CustomerJourney]:
        """Get journeys with optional type filter."""
        query = (
            select(CustomerJourney)
            .where(CustomerJourney.store_id == store_id)
            .options(selectinload(CustomerJourney.journey_events))
        )
        if journey_type:
            query = query.where(CustomerJourney.journey_type == journey_type)
        query = query.order_by(CustomerJourney.entry_time.desc())
        query = query.limit(limit).offset(offset)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_journey_analytics(
        self, store_id: uuid.UUID
    ) -> Dict:
        """Compute journey analytics for a store."""
        result = await self.db.execute(
            select(
                CustomerJourney.journey_type,
                func.count(CustomerJourney.id).label("count"),
                func.avg(CustomerJourney.duration_seconds).label("avg_duration"),
                func.avg(CustomerJourney.zone_count).label("avg_zones"),
            )
            .where(CustomerJourney.store_id == store_id)
            .group_by(CustomerJourney.journey_type)
        )
        rows = result.all()

        total = sum(r.count for r in rows)
        type_counts = {r.journey_type: r.count for r in rows}

        return {
            "total_journeys": total,
            "avg_journey_duration": (
                sum(r.avg_duration or 0 for r in rows) / len(rows)
                if rows else 0
            ),
            "avg_zones_visited": (
                sum(r.avg_zones or 0 for r in rows) / len(rows)
                if rows else 0
            ),
            "conversion_journeys": type_counts.get("conversion", 0),
            "abandonment_journeys": type_counts.get("abandonment", 0),
            "browse_journeys": type_counts.get("browse", 0),
            "bounce_journeys": type_counts.get("bounce", 0),
            "conversion_rate": (
                type_counts.get("conversion", 0) / total * 100
                if total > 0 else 0
            ),
        }

    async def get_top_paths(
        self, store_id: uuid.UUID, limit: int = 10
    ) -> List[Dict]:
        """Get the most common customer paths through the store."""
        result = await self.db.execute(
            select(
                CustomerJourney.zones_visited,
                CustomerJourney.journey_type,
                CustomerJourney.duration_seconds,
            )
            .where(
                CustomerJourney.store_id == store_id,
                CustomerJourney.zones_visited.isnot(None),
            )
        )
        journeys = result.all()

        # Count paths
        path_counter: Counter = Counter()
        path_durations: Dict[str, List[float]] = {}
        path_conversions: Dict[str, int] = {}

        for j in journeys:
            if not j.zones_visited:
                continue
            path_key = " → ".join(["ENTRY"] + j.zones_visited + ["EXIT"])
            path_counter[path_key] += 1
            if path_key not in path_durations:
                path_durations[path_key] = []
                path_conversions[path_key] = 0
            if j.duration_seconds:
                path_durations[path_key].append(j.duration_seconds)
            if j.journey_type == "conversion":
                path_conversions[path_key] += 1

        top_paths = []
        for path, count in path_counter.most_common(limit):
            durations = path_durations.get(path, [])
            conversions = path_conversions.get(path, 0)
            top_paths.append({
                "path": path.split(" → "),
                "count": count,
                "avg_duration_seconds": (
                    sum(durations) / len(durations) if durations else 0
                ),
                "conversion_rate": (
                    conversions / count * 100 if count > 0 else 0
                ),
            })

        return top_paths
