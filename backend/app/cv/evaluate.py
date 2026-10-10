"""Compare pipeline output with hand-counted ground truth.

    python -m app.cv.evaluate eval/public_clips.json --media-dir DIR [--fps 5]

The ground-truth file lists clips, the camera layout to use for each and the
expected counts (visitors = distinct people, entries = entry-line crossings,
zone visits and per-visit dwell). Videos are read from ``--media-dir`` and are
never stored in the repository. Prints one row per clip and exits non-zero if
any expected value is missed, so it can gate a model or tracker change.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

from app.cv.event_engine import EntryLine
from app.cv.pipeline import PipelineConfig, run_pipeline
from app.cv.zone_mapper import ZonePolygon


def _camera(spec: dict):
    zones = [
        ZonePolygon(name=z["name"], zone_type=z["zone_type"].upper(),
                    polygon=[tuple(p) for p in z["polygon"]], priority=z.get("priority", 0))
        for z in spec.get("zones", [])
    ]
    return zones, EntryLine.from_dict(spec.get("entry_line"))


def evaluate_clip(clip: dict, media_dir: Path, cfg: PipelineConfig) -> dict:
    zones, line = _camera(clip["camera"])
    result = run_pipeline(str(media_dir / clip["file"]), zones, line, cfg)
    types = Counter(e.event_type for e in result.events)
    exp = clip["expected"]
    got: dict = {"visitors": result.stats.get("tracks_created")}
    if "entries" in exp:
        got["entries"] = types.get("ENTRY", 0)
    checks = {k: got[k] == exp[k] for k in got if k in exp}

    if "zone_visits" in exp:
        visits = Counter(e.zone_name for e in result.events if e.event_type == "ZONE_ENTER")
        got["zone_visits"] = dict(visits)
        checks["zone_visits"] = all(visits.get(z, 0) == n for z, n in exp["zone_visits"].items())
    if "dwell_seconds" in exp:
        tol = exp.get("dwell_tolerance_seconds", 2)
        dwell_ok = True
        got["dwell_seconds"] = {}
        for zone, expected in exp["dwell_seconds"].items():
            seen = [round(e.dwell_seconds, 1) for e in result.events
                    if e.event_type == "ZONE_EXIT" and e.zone_name == zone and e.dwell_seconds is not None]
            got["dwell_seconds"][zone] = seen
            dwell_ok &= len(seen) == len(expected) and all(abs(a - b) <= tol for a, b in zip(seen, expected))
        checks["dwell_seconds"] = dwell_ok

    return {"clip": clip["name"], "expected": exp, "got": got, "checks": checks,
            "realtime_factor": result.stats.get("realtime_factor"), "peak_rss_mb": result.stats.get("peak_rss_mb")}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("truth", type=Path)
    parser.add_argument("--media-dir", type=Path, required=True)
    parser.add_argument("--fps", type=float, default=None)
    parser.add_argument("--json", action="store_true", help="print full JSON results")
    args = parser.parse_args(argv)

    cfg = PipelineConfig()
    if args.fps:
        cfg.analysis_fps = args.fps
    clips = json.loads(args.truth.read_text(encoding="utf-8"))["clips"]
    results = []
    for clip in clips:
        if not (args.media_dir / clip["file"]).exists():
            print(f"SKIP {clip['name']}: {clip['file']} not found in {args.media_dir}", file=sys.stderr)
            continue
        results.append(evaluate_clip(clip, args.media_dir, cfg))

    if args.json:
        print(json.dumps(results, indent=2))
    for r in results:
        status = "PASS" if all(r["checks"].values()) else "FAIL"
        detail = ", ".join(f"{k} {r['got'][k]} vs {r['expected'][k]}" for k in r["checks"])
        print(f"{status} {r['clip']}: {detail} (x{r['realtime_factor']} realtime, {r['peak_rss_mb']} MB)")
    return 0 if results and all(all(r["checks"].values()) for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
