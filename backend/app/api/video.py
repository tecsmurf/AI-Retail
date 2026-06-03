"""
Video processing API endpoints.

Provides endpoints for uploading CCTV footage, processing it through
the CV pipeline, and retrieving the generated events.
"""

from __future__ import annotations

import json
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/video", tags=["Video Processing"])


class ProcessingResult(BaseModel):
    """Video processing result."""
    video_name: str
    store_code: str
    camera_id: str
    total_events: int
    event_breakdown: dict
    processing_time_seconds: float


class CVEvent(BaseModel):
    """A single CV-generated event."""
    event_type: str
    customer_id: str
    store_code: str
    camera_id: str
    timestamp: str
    zone_name: Optional[str] = None
    zone_type: Optional[str] = None
    confidence: Optional[float] = None
    dwell_seconds: Optional[float] = None
    queue_wait_seconds: Optional[float] = None


@router.get("/events", response_model=List[CVEvent])
async def get_cv_events(
    store_code: Optional[str] = None,
    event_type: Optional[str] = None,
    limit: int = 100,
):
    """Retrieve CV-generated events from processed footage."""
    events_file = Path("data/cv_events.jsonl")
    if not events_file.exists():
        return []

    events = []
    with open(events_file, "r") as f:
        for line in f:
            if not line.strip():
                continue
            event = json.loads(line)

            # Apply filters
            if store_code and event.get("store_code") != store_code:
                continue
            if event_type and event.get("event_type") != event_type:
                continue

            events.append(event)
            if len(events) >= limit:
                break

    return events


@router.get("/events/summary")
async def get_cv_summary():
    """Get a summary of all CV-processed events."""
    events_file = Path("data/cv_events.jsonl")
    if not events_file.exists():
        return {"total_events": 0, "message": "No events. Run video processing first."}

    events = []
    with open(events_file, "r") as f:
        for line in f:
            if line.strip():
                events.append(json.loads(line))

    if not events:
        return {"total_events": 0}

    # Aggregate
    type_counts = {}
    store_counts = {}
    for e in events:
        et = e["event_type"]
        sc = e["store_code"]
        type_counts[et] = type_counts.get(et, 0) + 1
        store_counts[sc] = store_counts.get(sc, 0) + 1

    return {
        "total_events": len(events),
        "event_types": type_counts,
        "store_breakdown": store_counts,
        "first_event": events[0]["timestamp"] if events else None,
        "last_event": events[-1]["timestamp"] if events else None,
    }


@router.post("/upload", response_model=ProcessingResult)
async def upload_and_process(
    file: UploadFile = File(...),
    store_code: str = Form(...),
    camera_id: str = Form(...),
    camera_type: str = Form(default="zone"),
):
    """
    Upload a video file and process it through the CV pipeline.

    Returns the processing results with event counts.
    """
    import time

    # Validate file type
    if not file.filename or not file.filename.endswith(('.mp4', '.avi', '.mov', '.mkv')):
        raise HTTPException(400, "Only video files (.mp4, .avi, .mov, .mkv) are supported")

    # Save uploaded file temporarily
    upload_dir = Path("uploads")
    upload_dir.mkdir(exist_ok=True)
    file_path = upload_dir / file.filename
    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    try:
        from app.cv.process_videos import CCTVProcessor
        from app.cv.zone_mapper import ZonePolygon

        # Use full-frame zone for generic processing
        zones = [
            ZonePolygon("Full Store", camera_type.upper(),
                        [(0, 0), (1920, 0), (1920, 1080), (0, 1080)])
        ]

        start_time = time.time()

        processor = CCTVProcessor(
            store_code=store_code,
            camera_id=camera_id,
            camera_type=camera_type,
            zones=zones,
            confidence=0.4,
            sample_rate=15,
        )

        events = processor.process_video(str(file_path))
        processing_time = time.time() - start_time

        # Append to events file
        data_dir = Path("data")
        data_dir.mkdir(exist_ok=True)
        with open(data_dir / "cv_events.jsonl", "a") as f:
            for event in events:
                f.write(json.dumps(event) + "\n")

        # Event breakdown
        type_counts = {}
        for e in events:
            et = e["event_type"]
            type_counts[et] = type_counts.get(et, 0) + 1

        return ProcessingResult(
            video_name=file.filename,
            store_code=store_code,
            camera_id=camera_id,
            total_events=len(events),
            event_breakdown=type_counts,
            processing_time_seconds=round(processing_time, 1),
        )

    finally:
        # Clean up uploaded file
        if file_path.exists():
            file_path.unlink()
