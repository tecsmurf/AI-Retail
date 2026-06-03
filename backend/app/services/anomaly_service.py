"""Anomaly detection service."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.event import Event
from app.models.anomaly import Anomaly, Alert


class AnomalyService:
    """Service for detecting operational anomalies."""

    # Thresholds
    LONG_QUEUE_THRESHOLD = 30  # seconds
    ABNORMAL_DWELL_THRESHOLD = 300  # 5 minutes
    TRAFFIC_DROP_THRESHOLD = 0.5  # 50% drop
    EMPTY_STORE_MINUTES = 15

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def detect_anomalies(
        self, store_id: uuid.UUID
    ) -> List[Dict]:
        """Run all anomaly detection checks."""
        anomalies = []

        queue_anomalies = await self._check_long_queues(store_id)
        anomalies.extend(queue_anomalies)

        dwell_anomalies = await self._check_abnormal_dwell(store_id)
        anomalies.extend(dwell_anomalies)

        traffic_anomalies = await self._check_traffic_drops(store_id)
        anomalies.extend(traffic_anomalies)

        # Store detected anomalies
        for a in anomalies:
            anomaly = Anomaly(
                store_id=store_id,
                anomaly_type=a["type"],
                severity=a["severity"],
                zone_name=a.get("zone_name"),
                description=a["description"],
                metric_value=a.get("metric_value"),
                threshold_value=a.get("threshold_value"),
                detected_at=datetime.utcnow(),
            )
            self.db.add(anomaly)

            alert = Alert(
                store_id=store_id,
                alert_type=a["type"],
                title=a["title"],
                message=a["description"],
                severity=a["severity"],
            )
            self.db.add(alert)

        await self.db.flush()
        return anomalies

    async def _check_long_queues(
        self, store_id: uuid.UUID
    ) -> List[Dict]:
        """Detect long queue wait times."""
        result = await self.db.execute(
            select(Event)
            .where(
                Event.store_id == store_id,
                Event.event_type.in_(["QUEUE_COMPLETED", "QUEUE_ABANDONED"]),
                Event.queue_wait_seconds > self.LONG_QUEUE_THRESHOLD,
                Event.timestamp >= datetime.utcnow() - timedelta(hours=1),
            )
        )
        long_waits = list(result.scalars().all())

        anomalies = []
        if len(long_waits) >= 3:
            avg_wait = sum(e.queue_wait_seconds or 0 for e in long_waits) / len(long_waits)
            anomalies.append({
                "type": "LONG_QUEUE",
                "severity": "high" if avg_wait > 60 else "medium",
                "title": "Long Queue Detected",
                "description": (
                    f"Average queue wait time is {avg_wait:.0f}s "
                    f"({len(long_waits)} customers waiting > {self.LONG_QUEUE_THRESHOLD}s)"
                ),
                "zone_name": "Billing",
                "metric_value": avg_wait,
                "threshold_value": float(self.LONG_QUEUE_THRESHOLD),
            })

        return anomalies

    async def _check_abnormal_dwell(
        self, store_id: uuid.UUID
    ) -> List[Dict]:
        """Detect abnormally long dwell times."""
        result = await self.db.execute(
            select(Event)
            .where(
                Event.store_id == store_id,
                Event.dwell_seconds > self.ABNORMAL_DWELL_THRESHOLD,
                Event.timestamp >= datetime.utcnow() - timedelta(hours=1),
            )
        )
        long_dwells = list(result.scalars().all())

        anomalies = []
        for event in long_dwells:
            anomalies.append({
                "type": "ABNORMAL_DWELL",
                "severity": "low",
                "title": f"Long Dwell in {event.zone_name or 'Unknown Zone'}",
                "description": (
                    f"Customer {event.customer_id} spent "
                    f"{event.dwell_seconds:.0f}s in {event.zone_name}"
                ),
                "zone_name": event.zone_name,
                "metric_value": event.dwell_seconds,
                "threshold_value": float(self.ABNORMAL_DWELL_THRESHOLD),
            })

        return anomalies

    async def _check_traffic_drops(
        self, store_id: uuid.UUID
    ) -> List[Dict]:
        """Detect sudden traffic drops."""
        now = datetime.utcnow()
        current_hour_start = now.replace(minute=0, second=0, microsecond=0)
        prev_hour_start = current_hour_start - timedelta(hours=1)

        # Current hour visitors
        current = await self.db.execute(
            select(func.count(func.distinct(Event.customer_id)))
            .where(
                Event.store_id == store_id,
                Event.event_type == "ENTRY",
                Event.timestamp >= current_hour_start,
            )
        )
        current_count = current.scalar() or 0

        # Previous hour visitors
        prev = await self.db.execute(
            select(func.count(func.distinct(Event.customer_id)))
            .where(
                Event.store_id == store_id,
                Event.event_type == "ENTRY",
                Event.timestamp >= prev_hour_start,
                Event.timestamp < current_hour_start,
            )
        )
        prev_count = prev.scalar() or 0

        anomalies = []
        if prev_count > 5 and current_count < prev_count * self.TRAFFIC_DROP_THRESHOLD:
            drop_pct = (1 - current_count / prev_count) * 100
            anomalies.append({
                "type": "TRAFFIC_DROP",
                "severity": "medium",
                "title": "Sudden Traffic Drop",
                "description": (
                    f"Visitor traffic dropped {drop_pct:.0f}% "
                    f"from {prev_count} to {current_count} visitors"
                ),
                "metric_value": float(current_count),
                "threshold_value": float(prev_count),
            })

        return anomalies

    # ── Querying ─────────────────────────────────────────────────

    async def get_anomalies(
        self,
        store_id: uuid.UUID,
        limit: int = 50,
        include_resolved: bool = False,
    ) -> List[Anomaly]:
        """Get anomalies for a store."""
        query = select(Anomaly).where(Anomaly.store_id == store_id)
        if not include_resolved:
            query = query.where(Anomaly.is_resolved.is_(False))
        query = query.order_by(Anomaly.detected_at.desc()).limit(limit)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_alerts(
        self,
        store_id: uuid.UUID,
        limit: int = 20,
        unread_only: bool = False,
    ) -> List[Alert]:
        """Get alerts for a store."""
        query = select(Alert).where(Alert.store_id == store_id)
        if unread_only:
            query = query.where(Alert.is_read.is_(False))
        query = query.order_by(Alert.created_at.desc()).limit(limit)

        result = await self.db.execute(query)
        return list(result.scalars().all())
