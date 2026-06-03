"""Analytics Pydantic schemas."""

from __future__ import annotations

from typing import List, Optional, Dict

from pydantic import BaseModel, Field


class HourlyFootfall(BaseModel):
    """Footfall for a specific hour."""
    hour: int  # 0-23
    visitors: int
    label: str  # "9 AM", "10 AM"


class FootfallAnalytics(BaseModel):
    """Footfall analytics for a store."""
    total_visitors: int = 0
    visitors_today: int = 0
    visitors_yesterday: int = 0
    visitors_this_week: int = 0
    peak_hour: Optional[str] = None
    peak_hour_visitors: int = 0
    hourly_breakdown: List[HourlyFootfall] = Field(default_factory=list)
    daily_trend: List[dict] = Field(default_factory=list)
    avg_daily_visitors: float = 0.0
    growth_rate: float = 0.0  # % change vs previous period


class ConversionAnalytics(BaseModel):
    """Conversion funnel analytics."""
    total_visitors: int = 0
    zone_visitors: int = 0
    product_interactions: int = 0
    billing_visitors: int = 0
    purchases: int = 0
    visitor_to_zone_rate: float = 0.0
    zone_to_interaction_rate: float = 0.0
    interaction_to_purchase_rate: float = 0.0
    overall_conversion_rate: float = 0.0
    revenue_per_visitor: float = 0.0
    avg_basket_value: float = 0.0


class QueueAnalytics(BaseModel):
    """Queue analytics."""
    avg_wait_seconds: float = 0.0
    max_wait_seconds: float = 0.0
    current_queue_length: int = 0
    abandonment_rate: float = 0.0
    total_served: int = 0
    total_abandoned: int = 0
    avg_queue_position: float = 0.0
    hourly_wait_times: List[dict] = Field(default_factory=list)


class ZoneRanking(BaseModel):
    """Zone ranking entry."""
    zone_name: str
    visits: int
    avg_dwell_seconds: float
    conversion_rate: float
    revenue: float
    rank: int


class StoreAnalytics(BaseModel):
    """Complete store analytics."""
    store_id: str
    store_name: str
    period: str  # "today", "week", "month"
    footfall: FootfallAnalytics
    conversion: ConversionAnalytics
    queue: QueueAnalytics
    zone_rankings: List[ZoneRanking] = Field(default_factory=list)
    demographics: Dict[str, int] = Field(default_factory=dict)
    revenue_total: float = 0.0
    top_brands: List[dict] = Field(default_factory=list)
