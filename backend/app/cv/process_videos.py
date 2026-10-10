"""Run the CV pipeline on a local video without the API or database.

    python -m app.cv.process_videos VIDEO --config camera.json [--out DIR] [--fps 5]

``camera.json`` describes one camera's zones and optional entry line in
normalized coordinates (0..1, origin top-left)::

    {
      "zones": [
        {"name": "Billing Queue", "zone_type": "QUEUE",
         "polygon": [[0.1, 0.5], [0.4, 0.5], [0.4, 0.9], [0.1, 0.9]], "priority": 1}
      ],
      "entry_line": {"p1": [0.2, 0.6], "p2": [0.8, 0.6], "inside": "right"}
    }

Writes ``events.jsonl``, ``occupancy.jsonl``, ``stats.json`` and the
pipeline's own artifacts (tracks, annotated snapshots) to ``--out``. Used
for validation runs and for debugging zone layouts before uploading.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from app.cv.event_engine import EntryLine
from app.cv.pipeline import PipelineConfig, run_pipeline
from app.cv.zone_mapper import ZonePolygon


def load_camera_config(path: Path):
    data = json.loads(path.read_text(encoding="utf-8"))
    zones = [
        ZonePolygon(
            name=z["name"], zone_type=z["zone_type"].upper(), polygon=[tuple(p) for p in z["polygon"]],
            priority=z.get("priority", 0), zone_id=z.get("zone_code"),
        )
        for z in data.get("zones", [])
    ]
    return zones, EntryLine.from_dict(data.get("entry_line"))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("video")
    parser.add_argument("--config", type=Path, help="camera zones/entry-line JSON (optional)")
    parser.add_argument("--out", type=Path, default=Path("cv_output"))
    parser.add_argument("--fps", type=float, default=None, help="analysis frames per second (default 5)")
    parser.add_argument("--max-seconds", type=float, default=None)
    args = parser.parse_args(argv)

    zones, line = load_camera_config(args.config) if args.config else ([], None)
    cfg = PipelineConfig()
    if args.fps:
        cfg.analysis_fps = args.fps
    if args.max_seconds:
        cfg.max_video_seconds = args.max_seconds
    args.out.mkdir(parents=True, exist_ok=True)

    def progress(fraction: float, _info: dict) -> None:
        print(f"\r{fraction * 100:5.1f}%", end="", file=sys.stderr, flush=True)

    result = run_pipeline(args.video, zones, line, cfg, progress=progress, artifact_dir=str(args.out))
    print(file=sys.stderr)
    with open(args.out / "events.jsonl", "w", encoding="utf-8") as f:
        for e in result.events:
            row = asdict(e)
            row.pop("box", None)
            f.write(json.dumps(row) + "\n")
    with open(args.out / "occupancy.jsonl", "w", encoding="utf-8") as f:
        for t, zone, ztype, count in result.occupancy:
            f.write(json.dumps({"t": t, "zone": zone, "zone_type": ztype, "count": count}) + "\n")
    (args.out / "stats.json").write_text(json.dumps({"stats": result.stats, "warnings": result.warnings}, indent=2))
    keys = ("events", "tracks_created", "frames_analyzed", "realtime_factor", "peak_rss_mb", "device")
    print(json.dumps({k: result.stats.get(k) for k in keys}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
