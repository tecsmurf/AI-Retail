"""Analytics service — computed metrics for stores, zones, and conversions."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from sqlalchemy import select, func, and_, case, distinct
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.event import Event, CustomerJourney
from app.models.pos import POSTransaction
from app.models.store import Zone


class AnalyticsService:
    """Service for computing retail analytics."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ── Footfall ─────────────────────────────────────────────────

    async def get_footfall(
        self,
        store_id: uuid.UUID,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> Dict:
        """Compute footfall analytics."""
        now = datetime.utcnow()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        yesterday_start = today_start - timedelta(days=1)
        week_start = today_start - timedelta(days=7)

        # Total visitors today
        visitors_today = await self._count_visitors(
            store_id, today_start, now
        )
        visitors_yesterday = await self._count_visitors(
            store_id, yesterday_start, today_start
        )
        visitors_week = await self._count_visitors(
            store_id, week_start, now
        )

        # Hourly breakdown for today
        hourly = await self._hourly_breakdown(store_id, today_start, now)

        # Peak hour
        peak = max(hourly, key=lambda x: x["visitors"]) if hourly else None

        # Growth rate
        growth = 0.0
        if visitors_yesterday > 0:
            growth = ((visitors_today - visitors_yesterday) / visitors_yesterday) * 100

        return {
            "total_visitors": visitors_week,
            "visitors_today": visitors_today,
            "visitors_yesterday": visitors_yesterday,
            "visitors_this_week": visitors_week,
            "peak_hour": peak["label"] if peak and peak["visitors"] > 0 else None,
            "peak_hour_visitors": peak["visitors"] if peak else 0,
            "hourly_breakdown": hourly,
            "avg_daily_visitors": visitors_week / 7 if visitors_week else 0,
            "growth_rate": round(growth, 1),
        }

    async def _count_visitors(
        self,
        store_id: uuid.UUID,
        start: datetime,
        end: datetime,
    ) -> int:
        """Count unique visitors in a time range."""
        result = await self.db.execute(
            select(func.count(distinct(Event.customer_id)))
            .where(
                Event.store_id == store_id,
                Event.event_type == "ENTRY",
                Event.is_staff.is_(False),
                Event.timestamp >= start,
                Event.timestamp < end,
            )
        )
        return result.scalar() or 0

    async def _hourly_breakdown(
        self,
        store_id: uuid.UUID,
        start: datetime,
        end: datetime,
    ) -> List[Dict]:
        """Get hourly visitor breakdown."""
        result = await self.db.execute(
            select(
                func.extract("hour", Event.timestamp).label("hour"),
                func.count(distinct(Event.customer_id)).label("visitors"),
            )
            .where(
                Event.store_id == store_id,
                Event.event_type == "ENTRY",
                Event.is_staff.is_(False),
                Event.timestamp >= start,
                Event.timestamp < end,
            )
            .group_by(func.extract("hour", Event.timestamp))
        )

        hour_labels = [
            "12 AM", "1 AM", "2 AM", "3 AM", "4 AM", "5 AM",
            "6 AM", "7 AM", "8 AM", "9 AM", "10 AM", "11 AM",
            "12 PM", "1 PM", "2 PM", "3 PM", "4 PM", "5 PM",
            "6 PM", "7 PM", "8 PM", "9 PM", "10 PM", "11 PM",
        ]

        hourly = {int(r.hour): r.visitors for r in result}
        return [
            {"hour": h, "visitors": hourly.get(h, 0), "label": hour_labels[h]}
            for h in range(24)
        ]

    # ── Zone Analytics ───────────────────────────────────────────

    async def get_zone_analytics(
        self, store_id: uuid.UUID
    ) -> List[Dict]:
        """Compute analytics for each zone in a store."""
        result = await self.db.execute(
            select(
                Event.zone_name,
                Event.zone_type,
                func.count(Event.id).label("total_events"),
                func.count(distinct(Event.customer_id)).label("unique_visitors"),
                func.avg(Event.dwell_seconds).label("avg_dwell"),
                func.max(Event.dwell_seconds).label("max_dwell"),
            )
            .where(
                Event.store_id == store_id,
                Event.zone_name.isnot(None),
                Event.event_type.in_(["ZONE_ENTER", "ZONE_ENTERED", "ZONE_EXIT", "ZONE_EXITED"]),
            )
            .group_by(Event.zone_name, Event.zone_type)
            .order_by(func.count(distinct(Event.customer_id)).desc())
        )
        rows = result.all()

        zones = []
        for rank, row in enumerate(rows, 1):
            zones.append({
                "zone_name": row.zone_name,
                "zone_type": row.zone_type or "SHELF",
                "total_visits": row.total_events // 2,  # enter + exit = 1 visit
                "unique_visitors": row.unique_visitors,
                "avg_dwell_seconds": round(float(row.avg_dwell or 0), 1),
                "max_dwell_seconds": round(float(row.max_dwell or 0), 1),
                "popularity_rank": rank,
            })

        return zones

    # ── Conversion Analytics ─────────────────────────────────────

    async def get_conversion_analytics(
        self, store_id: uuid.UUID
    ) -> Dict:
        """Compute conversion funnel metrics."""
        # Total visitors (ENTRY events)
        total_visitors = await self._count_visitors(
            store_id,
            datetime.utcnow() - timedelta(days=30),
            datetime.utcnow(),
        )

        # Zone visitors
        zone_result = await self.db.execute(
            select(func.count(distinct(Event.customer_id)))
            .where(
                Event.store_id == store_id,
                Event.event_type.in_(["ZONE_ENTER", "ZONE_ENTERED"]),
            )
        )
        zone_visitors = zone_result.scalar() or 0

        # Billing visitors
        billing_result = await self.db.execute(
            select(func.count(distinct(Event.customer_id)))
            .where(
                Event.store_id == store_id,
                Event.event_type.in_(
                    ["CHECKOUT", "QUEUE_COMPLETED", "QUEUE_ENTER"]
                ),
            )
        )
        billing_visitors = billing_result.scalar() or 0

        # Revenue
        revenue_result = await self.db.execute(
            select(func.sum(POSTransaction.total_amount))
            .where(POSTransaction.store_id == store_id)
        )
        total_revenue = revenue_result.scalar() or 0

        # Purchase count (unique orders)
        purchase_result = await self.db.execute(
            select(func.count(distinct(POSTransaction.order_id)))
            .where(POSTransaction.store_id == store_id)
        )
        purchases = purchase_result.scalar() or 0

        return {
            "total_visitors": total_visitors,
            "zone_visitors": zone_visitors,
            "product_interactions": 0,  # Phase 2
            "billing_visitors": billing_visitors,
            "purchases": purchases,
            "visitor_to_zone_rate": (
                round(zone_visitors / total_visitors * 100, 1)
                if total_visitors > 0 else 0
            ),
            "overall_conversion_rate": (
                round(purchases / total_visitors * 100, 1)
                if total_visitors > 0 else 0
            ),
            "revenue_per_visitor": (
                round(total_revenue / total_visitors, 2)
                if total_visitors > 0 else 0
            ),
            "avg_basket_value": (
                round(total_revenue / purchases, 2)
                if purchases > 0 else 0
            ),
        }

    # ── Queue Analytics ──────────────────────────────────────────

    async def get_queue_analytics(
        self, store_id: uuid.UUID
    ) -> Dict:
        """Compute queue analytics."""
        result = await self.db.execute(
            select(
                func.avg(Event.queue_wait_seconds).label("avg_wait"),
                func.max(Event.queue_wait_seconds).label("max_wait"),
                func.count(Event.id).label("total"),
                func.sum(
                    case(
                        (Event.queue_abandoned.is_(True), 1),
                        else_=0,
                    )
                ).label("abandoned"),
            )
            .where(
                Event.store_id == store_id,
                Event.event_type.in_(["QUEUE_COMPLETED", "QUEUE_ABANDONED"]),
            )
        )
        row = result.one_or_none()

        if not row or not row.total:
            return {
                "avg_wait_seconds": 0,
                "max_wait_seconds": 0,
                "current_queue_length": 0,
                "abandonment_rate": 0,
                "total_served": 0,
                "total_abandoned": 0,
            }

        total = row.total or 0
        abandoned = row.abandoned or 0

        return {
            "avg_wait_seconds": round(float(row.avg_wait or 0), 1),
            "max_wait_seconds": round(float(row.max_wait or 0), 1),
            "current_queue_length": 0,
            "abandonment_rate": round(abandoned / total * 100, 1) if total > 0 else 0,
            "total_served": total - abandoned,
            "total_abandoned": abandoned,
        }

    # ── Demographics ─────────────────────────────────────────────

    async def get_demographics(
        self, store_id: uuid.UUID
    ) -> Dict:
        """Get demographic breakdown of visitors."""
        # Gender
        gender_result = await self.db.execute(
            select(
                Event.gender,
                func.count(distinct(Event.customer_id)).label("count"),
            )
            .where(
                Event.store_id == store_id,
                Event.event_type == "ENTRY",
                Event.gender.isnot(None),
            )
            .group_by(Event.gender)
        )
        gender = {r.gender: r.count for r in gender_result}

        # Age buckets
        age_result = await self.db.execute(
            select(
                Event.age_bucket,
                func.count(distinct(Event.customer_id)).label("count"),
            )
            .where(
                Event.store_id == store_id,
                Event.event_type == "ENTRY",
                Event.age_bucket.isnot(None),
            )
            .group_by(Event.age_bucket)
        )
        age_buckets = {r.age_bucket: r.count for r in age_result}

        return {
            "gender": gender,
            "age_buckets": age_buckets,
        }

    # ── POS / Revenue ────────────────────────────────────────────

    async def get_revenue_analytics(
        self, store_id: uuid.UUID
    ) -> Dict:
        """Revenue analytics from POS data."""
        # Use store_id as string for POS table (matches CSV format)
        result = await self.db.execute(
            select(
                func.sum(POSTransaction.total_amount).label("total_revenue"),
                func.count(distinct(POSTransaction.order_id)).label("total_orders"),
                func.count(POSTransaction.id).label("total_items"),
            )
            .where(POSTransaction.store_id == str(store_id))
        )
        row = result.one_or_none()

        # Top brands
        brand_result = await self.db.execute(
            select(
                POSTransaction.brand_name,
                func.sum(POSTransaction.total_amount).label("revenue"),
                func.count(POSTransaction.id).label("items_sold"),
            )
            .where(POSTransaction.store_id == str(store_id))
            .group_by(POSTransaction.brand_name)
            .order_by(func.sum(POSTransaction.total_amount).desc())
            .limit(10)
        )
        brands = [
            {
                "brand": r.brand_name,
                "revenue": round(float(r.revenue or 0), 2),
                "items_sold": r.items_sold,
            }
            for r in brand_result
        ]

        return {
            "total_revenue": round(float(row.total_revenue or 0), 2) if row else 0,
            "total_orders": row.total_orders if row else 0,
            "total_items": row.total_items if row else 0,
            "avg_order_value": (
                round(float(row.total_revenue or 0) / row.total_orders, 2)
                if row and row.total_orders > 0 else 0
            ),
            "top_brands": brands,
        }
