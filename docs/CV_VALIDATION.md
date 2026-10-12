# CV validation

Status: **validated on public sample clips only.** The pipeline has not yet been
measured on PurpleSol's own store footage, so none of the numbers below should be
read as store accuracy. Re-run the same procedure on store clips before relying on
footfall figures.

## What was tested

| Item | Value |
|---|---|
| Detector | YOLO11n (`yolo11n.pt`), person class only |
| Tracker | supervision ByteTrack, `minimum_matching_threshold` 0.8 |
| Analysis rate | 5 fps (default) and 10 fps |
| Hardware | 4 vCPU cloud container, CPU only, no GPU |
| Clips | 4 public Intel IoT sample videos (github.com/intel-iot-devkit/sample-videos) |

The clips are staged scenes (people walking into a room, standing at a table, a
store aisle). They are well lit, overhead or eye level, with at most 5 people in
frame. Real CCTV is usually lower resolution, more compressed, more crowded and
partly occluded, so expect store results to be worse.

**Who made the ground truth:** the counts were made by the AI agent that built the
pipeline, by viewing frame strips (one frame every 1 to 2 seconds) and annotated
contact sheets. No human annotator has checked them. Treat them as a sanity check,
not a benchmark.

## Results

### 1. Detection (per frame)

12 evenly spaced frames per clip, detections at confidence 0.35, compared with the
number of people visible in each frame.

| Clip | People visible | Detected correctly | Missed | False boxes |
|---|---|---|---|---|
| store-aisle-detection | 41 | 39 | 2 | 0 |
| people-detection | 8 | 7 | 1 | 0 |
| one-by-one-person-detection | 9 | 9 | 0 | 0 |
| **Total** | **58** | **55** | **3** | **0** |

Precision 1.00, recall 0.95 (55/58) on 36 frames. Mean absolute count error is
0.08 people per frame.

All 3 misses were people only partly in view: a head and shoulder at the frame
edge, a person mostly hidden behind two others, and the top of a head entering at
the bottom edge. The sample is small (58 people), so the true recall could easily
be several points lower.

### 2. Counting and tracking (whole clip)

Reproduce with:

```bash
cd backend
python -m app.cv.evaluate eval/public_clips.json --media-dir /path/to/clips
```

| Clip | Check | Expected | Pipeline (5 fps) | Result |
|---|---|---|---|---|
| one-by-one | distinct visitors (tracks) | 6 | 6 | PASS |
| one-by-one | entries across a line near the bottom edge | 6 | 6 | PASS |
| one-by-one | visits to the table zone | 6 | 6 | PASS |
| one-by-one | dwell per visit, seconds (±3 s) | 12, 20, 17, 11, 25, 11 | 12.6, 20.8, 18.4, 11.4, 26.4, 11.8 | PASS |
| people-detection | distinct visitors | 7 | 7 | PASS |
| people-detection | entries across a line at 75% height | 7 | 7 | PASS |
| face-demographics-walking | distinct visitors | 7 | 7 | PASS |

The same counts came out at 10 fps. There were no identity switches or duplicate
tracks on these clips: each person produced exactly one track.

The expected dwell values were read from 2-second frame strips, so they are only
accurate to about ±2 s. The pipeline is consistently 0.5 to 1.5 s longer because
the zone polygon includes the last steps of the approach to the table.

### 3. Speed and memory

| Clip | Length | Realtime factor at 5 fps | Realtime factor at 10 fps | Peak RSS |
|---|---|---|---|---|
| one-by-one | 139 s | 3.5 to 3.7x | 2.0x | 660 MB |
| people-detection | 50 s | 3.2 to 4.0x | 1.8x | 660 MB |
| face-demographics-walking | 61 s | 3.3 to 4.2x | 1.9x | 660 MB |
| store-aisle (via the worker) | 65 s | 3.2x | not run | not recorded |

"3.5x" means one hour of video takes about 17 minutes on 4 CPU cores. A worker
needs at least 1 GB of RAM. Speed will differ on Railway's CPUs; check the
`realtime_factor` that every finished job reports on the Videos page.

## Findings that affect setup

1. **The entry line has to be drawn where feet actually cross it.** The first lab
   run of one-by-one used a vertical line down the middle and recorded 2 events for
   6 visitors, because people walk up and down the frame, never across it. Moving
   the line to the bottom edge gave 6 of 6. This was a configuration mistake, not a
   detection failure. The zone editor shows the line on a real frame for this
   reason.
2. **Some camera angles cannot count entries with a line at all.** In
   face-demographics-walking, people walk toward the camera and their feet are
   already in the bottom 14% of the frame when first seen, then leave the frame.
   No line is crossed, so the pipeline correctly reports 0 entries, even though it
   tracked all 7 people. Entrance cameras should look across or down at the door,
   not straight along the walking direction.
3. **Fast movement can split a track.** In synthetic tests at 5 fps, ByteTrack lost
   a person whose box moved more than about 0.4 to 0.5 box widths between analysed
   frames (21 px on a 40 px box). A threshold of 0.9 tolerated 21 px and 0.95
   tolerated 26 px. None of the public clips triggered this, so the default stays
   at 0.8. If store entrance footage shows duplicate visitors, first try
   `ANALYSIS_FPS=10` (about half the speed), then a matching threshold of 0.9.
4. **Partly visible people are the main source of misses.** People cut off by the
   frame edge or hidden behind others are missed. Store counts will be low in
   crowded scenes.

## Not yet measured

* Accuracy on PurpleSol's own CCTV clips (8 clips, about 775 MB). They are on the
  owner's PC, which was offline during this work. When it is reachable, add each
  clip and its camera layout to a private ground-truth file (do not commit the
  footage) and run `app.cv.evaluate` on it.
* Multi-object tracking metrics (IDF1, MOTA). These need per-frame boxes with
  identities. `motmetrics` is installed for this, but no such annotation exists
  yet.
* Queue wait and abandonment on real billing footage. They are only covered by
  unit tests on synthetic tracks (`tests/test_cv_logic.py`,
  `tests/test_video_pipeline.py`).
* Larger models. `yolo11s` should recover some partly visible people at roughly
  2 to 3 times the CPU cost. It has not been compared on these clips.
* Night, IR, rain, glare and very crowded scenes.
