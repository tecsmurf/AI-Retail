"""Store-local date ranges -> naive UTC bounds.

Analytics endpoints accept ``start`` and ``end`` as *local calendar dates* of
the store (inclusive). They are converted to a half-open UTC interval
``[start 00:00 local, (end + 1 day) 00:00 local)`` using the store's IANA time
zone, so day and hour boundaries are the store's, not the server's.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Iterable, List, Optional, Sequence
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import HTTPException

from app.models.event import REAL_SOURCES

MAX_RANGE_DAYS = 366


def store_tz(name: Optional[str]) -> ZoneInfo:
    try:
        return ZoneInfo(name or "UTC")
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo("UTC")


def to_utc_naive(local: datetime, tz: ZoneInfo) -> datetime:
    return local.replace(tzinfo=tz).astimezone(UTC).replace(tzinfo=None)


def to_local(utc_naive: datetime, tz: ZoneInfo) -> datetime:
    return utc_naive.replace(tzinfo=UTC).astimezone(tz)


@dataclass
class TimeRange:
    start_date: date
    end_date: date  # inclusive
    tz: ZoneInfo
    start_utc: datetime
    end_utc: datetime  # exclusive

    @property
    def days(self) -> int:
        return (self.end_date - self.start_date).days + 1

    def as_dict(self) -> dict:
        return {
            "start": self.start_date.isoformat(),
            "end": self.end_date.isoformat(),
            "timezone": str(self.tz.key),
            "start_utc": self.start_utc.isoformat() + "Z",
            "end_utc": self.end_utc.isoformat() + "Z",
        }

    def local_days(self) -> List[date]:
        return [self.start_date + timedelta(days=i) for i in range(self.days)]


def resolve_range(
    tz_name: Optional[str],
    start: Optional[date],
    end: Optional[date],
    default_days: int = 7,
    today: Optional[date] = None,
) -> TimeRange:
    tz = store_tz(tz_name)
    if today is None:
        today = datetime.now(tz).date()
    if end is None:
        end = start + timedelta(days=default_days - 1) if start else today
    if start is None:
        start = end - timedelta(days=default_days - 1)
    if start > end:
        raise HTTPException(422, "start must be on or before end")
    if (end - start).days + 1 > MAX_RANGE_DAYS:
        raise HTTPException(422, f"date range is limited to {MAX_RANGE_DAYS} days")
    start_utc = to_utc_naive(datetime.combine(start, time.min), tz)
    end_utc = to_utc_naive(datetime.combine(end + timedelta(days=1), time.min), tz)
    return TimeRange(start, end, tz, start_utc, end_utc)


def parse_sources(data: str) -> Sequence[str]:
    """``data=real`` (default): CV + API events only. ``data=all`` also
    includes the bundled sample, demo and legacy v1 records."""
    if data == "real":
        return REAL_SOURCES
    if data == "all":
        return ("cv", "api", "sample", "demo", "legacy_cv")
    parts = tuple(p.strip() for p in data.split(",") if p.strip())
    allowed = {"cv", "api", "sample", "demo", "legacy_cv"}
    if not parts or any(p not in allowed for p in parts):
        raise HTTPException(422, "data must be 'real', 'all', or a comma list of cv,api,sample,demo,legacy_cv")
    return parts


def hour_label(h: int) -> str:
    suffix = "AM" if h < 12 else "PM"
    hh = h % 12 or 12
    return f"{hh} {suffix}"


def percentile(values: Iterable[float], q: float) -> Optional[float]:
    vals = sorted(values)
    if not vals:
        return None
    k = (len(vals) - 1) * q
    lo, hi = int(k), min(int(k) + 1, len(vals) - 1)
    return vals[lo] + (vals[hi] - vals[lo]) * (k - lo)
