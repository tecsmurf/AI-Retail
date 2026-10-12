"""Evidence-backed insights.

Each insight is a deterministic rule over metrics already shown on the
dashboard, carries the numbers it is based on, and states its confidence from
the sample size. When the data is too thin, the rule says so instead of
producing a recommendation. No language model is involved.
"""

from __future__ import annotations

from typing import Dict, List

MIN_VISITS = 30
MIN_ENTRIES = 50
MIN_QUEUE = 20


def _confidence(n: int, solid: int) -> str:
    if n >= solid * 3:
        return "high"
    if n >= solid:
        return "medium"
    return "low"


def build_insights(ov: Dict, ja: Dict) -> Dict:
    items: List[Dict] = []
    gaps: List[str] = []
    ff = ov["footfall"]
    zones = ov["zones"]
    q = ov["queue"]
    conv = ov["conversion"]

    # Peak hour
    if ff["entries"] >= MIN_ENTRIES and ff["peak_hour"]:
        share = ff["peak_hour_entries"] / ff["entries"] * 100
        items.append({
            "id": "peak_hour", "category": "staffing",
            "title": f"Busiest hour: {ff['peak_hour']}",
            "detail": f"{ff['peak_hour_entries']} of {ff['entries']} entries ({share:.0f}%) happened in this hour. "
                      "Consider aligning floor and billing staff with it.",
            "evidence": {"entries": ff["entries"], "peak_hour_entries": ff["peak_hour_entries"]},
            "confidence": _confidence(ff["entries"], MIN_ENTRIES),
        })
    else:
        gaps.append(f"Peak-hour analysis needs at least {MIN_ENTRIES} entries (have {ff['entries']}).")

    # Zone engagement
    visited = [z for z in zones if z["visits"] >= 5]
    total_visits = sum(z["visits"] for z in zones)
    if total_visits >= MIN_VISITS and len(visited) >= 2:
        top = max(visited, key=lambda z: z["visits"])
        low = min(visited, key=lambda z: z["visits"])
        items.append({
            "id": "zone_traffic", "category": "merchandising",
            "title": f"{top['zone_name']} draws the most visits; {low['zone_name']} the fewest",
            "detail": f"{top['zone_name']}: {top['visits']} visits, {low['zone_name']}: {low['visits']} visits. "
                      "Low traffic can reflect placement or camera coverage; check both before moving stock.",
            "evidence": {"top_zone_visits": top["visits"], "low_zone_visits": low["visits"], "total_visits": total_visits},
            "confidence": _confidence(total_visits, MIN_VISITS),
        })
        dwell = [z for z in visited if z["median_dwell_seconds"] is not None]
        if len(dwell) >= 2:
            longest = max(dwell, key=lambda z: z["median_dwell_seconds"])
            items.append({
                "id": "zone_dwell", "category": "engagement",
                "title": f"Longest engagement: {longest['zone_name']}",
                "detail": f"Median dwell {longest['median_dwell_seconds']:.0f}s over {longest['visits']} visits.",
                "evidence": {"median_dwell_seconds": longest["median_dwell_seconds"], "visits": longest["visits"]},
                "confidence": _confidence(longest["visits"], MIN_VISITS // 2),
            })
    else:
        gaps.append(f"Zone comparisons need at least {MIN_VISITS} zone visits across 2+ zones (have {total_visits}).")

    # Queue
    if q["queue_visits"] >= MIN_QUEUE and q["p90_wait_seconds"] is not None:
        items.append({
            "id": "queue_wait", "category": "operations",
            "title": f"90% of queue waits are under {q['p90_wait_seconds']:.0f}s",
            "detail": f"Median wait {q['median_wait_seconds']:.0f}s over {q['queue_visits']} observed queue visits; "
                      f"max {q['max_wait_seconds']:.0f}s.",
            "evidence": {k: q[k] for k in ("queue_visits", "median_wait_seconds", "p90_wait_seconds", "max_wait_seconds")},
            "confidence": _confidence(q["queue_visits"], MIN_QUEUE),
        })
        if q["abandoned"] or q["completed"]:
            items.append({
                "id": "queue_abandonment", "category": "operations",
                "title": f"Possible queue abandonment: {q['abandonment_rate']}%",
                "detail": "Inferred from people leaving the queue without reaching the counter on camera. "
                          f"{q['abandoned']} abandoned vs {q['completed']} reached the counter; "
                          f"{q['outcome_unknown']} outcomes unknown (track lost).",
                "evidence": {k: q[k] for k in ("abandoned", "completed", "outcome_unknown")},
                "confidence": "low",
            })
    else:
        gaps.append(f"Queue insights need at least {MIN_QUEUE} observed queue visits (have {q['queue_visits']}).")

    if conv["conversion_rate"] is None:
        gaps.extend(conv["notes"])

    return {"insights": items, "insufficient_data": gaps, "journeys_considered": ja.get("total_journeys", 0),
            "method": "Deterministic rules over persisted metrics; see each item's evidence."}
