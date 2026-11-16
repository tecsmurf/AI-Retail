# CV validation

Status: **validated on public sample clips only.** The pipeline has not yet been
measured on PurpleSol's own store footage, so none of the numbers below should be
read as store accuracy. Re-run the same procedure on store clips before relying on
footfall figures.

## What was tested

| Item | Value |
|---|---|
| Detector | YOLO11n (`yolo11n.pt`), person class only (YOLO26s since pipeline 2.2, see below) |
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

## Detector upgrade to YOLO26s (pipeline 2.2, 2026-11-11)

The public clips are too easy to separate detectors (every model passes them),
so models were compared on a labelled benchmark: 1,000 COCO val2017 images that
contain people (fixed seed, same images for every model), person class only,
scored with the official COCO evaluator. "CCTV-like" is the same images at half
resolution and JPEG quality 30, scaled back, to imitate a compressed CCTV
substream. CPU time is per image at 640 px on 4 vCPU (no GPU), Ultralytics
8.4.210. Reproduce with `python eval/coco_person_benchmark.py COCO_DIR MODEL clean|cctv`.

| Model | Person AP clean | AP50 clean | Person AP CCTV-like | AP50 CCTV-like | Recall at conf 0.35, CCTV-like | Small people AP, CCTV-like | CPU ms/image |
|---|---|---|---|---|---|---|---|
| YOLO11n (old default) | 0.523 | 0.775 | 0.327 | 0.561 | 0.257 | 0.108 | 45 |
| YOLO26n | 0.521 | 0.777 | 0.322 | 0.556 | 0.243 | 0.105 | 41 |
| YOLO12n | 0.526 | 0.775 | 0.335 | 0.574 | 0.245 | 0.105 | 58 |
| YOLO11s | 0.580 | 0.821 | 0.375 | 0.611 | 0.299 | 0.129 | 97 |
| **YOLO26s (new default)** | **0.599** | **0.841** | **0.400** | **0.638** | **0.316** | **0.143** | **94** |
| YOLO12s | 0.585 | 0.824 | 0.386 | 0.621 | 0.289 | 0.132 | 112 |
| YOLO11m | 0.623 | 0.853 | 0.407 | 0.641 | 0.319 | 0.141 | 209 |
| YOLO26m | 0.632 | 0.865 | 0.431 | 0.662 | 0.343 | 0.167 | 221 |

* YOLO26s is the most accurate of the models that keep a CPU worker faster
  than realtime: +7.6 AP clean and +7.3 AP on the CCTV-like images over YOLO11n,
  and it finds about a quarter more people above the 0.35 threshold on degraded
  frames (0.316 vs 0.257 recall). It costs about twice the CPU of YOLO11n.
* YOLO26m is the most accurate overall, but at 5 fps it needs about 1.1 s of
  CPU per second of video on 4 vCPU, which is slower than realtime. Use it on a
  GPU worker or in-store box with a GPU (`YOLO_MODEL=yolo26m.pt`).
* The nano models are all within about 1 AP of each other; YOLO12 is slower
  than YOLO11 and YOLO26 on CPU at every size.

Full pipeline with YOLO26s on the public clips: all checks pass at 5, 2.5 fps
(YOLO11n missed one at 2.5 fps: 8 visitors for 7) and the stress replay gives
the same errors as YOLO11n within one count (these clips cannot separate the
detectors). Speed through the whole pipeline at 5 fps: about 2.5 to 2.8x
realtime (YOLO11n: about 4.9x on the same machine), so one hour of video takes
about 22 minutes on 4 vCPU. Peak memory rose from about 650 MB to 720 MB.

COCO photos are not store CCTV. These numbers rank the models; they are not a
store accuracy figure. That still needs the store's own clips.

**Licence.** YOLO11, YOLO12 and YOLO26 weights and the Ultralytics library are
AGPL-3.0. Selling PurpleSol as a closed product needs either an Ultralytics
Enterprise licence or AGPL compliance. This was already true with YOLO11n.

## Pipeline 2.1 changes (2026-11-08)

Measured on the same clips and the same AI-made ground truth as above, so the
same caveats apply. Nothing here has been checked on store footage yet.

### What changed

1. **Tracker output bug fixed.** supervision's `update_with_detections` hands
   back a detection only if it overlaps the Kalman-filtered track box by IoU
   > 0.5. When someone speeds up, stops, or walks toward the camera, the filtered
   box lags behind, and the person disappeared from the output for up to 4 s
   while ByteTrack still tracked them internally (seen on one-by-one at
   2.5 fps, right where people cross the entry line). `PersonTracker` now
   joins every updated track to the detection ByteTrack actually matched it to.
2. **Tracks are reported from their first detection** (`minimum_consecutive_frames`
   1, was 2). With 2, a missed detection just after someone appeared delayed or
   killed the track, and people who crossed the entry line in their first
   frames were not counted.
3. **Short tracks are measured in time as well as samples**
   (`min_track_seconds` 0.5). This keeps one-frame flickers out at 10 fps, where
   change 2 alone produced one extra visitor on people-detection.
4. **Track stitching** (`app/cv/stitcher.py`). A new tracker id that appears
   within 2 s near where a lost visitor was heading, with a similar box size,
   continues that visitor instead of counting a new one. Tracks lost at the
   frame edge, far-away matches and ambiguous matches are never joined.
5. **Line crossing at track end.** Someone who crosses the entry line and leaves
   the view (or is lost) before two samples on the new side is still counted,
   unless they were jittering on the line.

### Results

`visitor err` and `entry err` are the summed absolute error over the three
clips (20 visitors, 13 entries per pass); "drop" rows discard that share of
detections at random, 5 seeds each, to imitate occlusion and blur. YOLO11n,
640 px, detections cached once and replayed through both versions.

| Stress | Version | Visitor error | Entry error | Clips fully right |
|---|---|---|---|---|
| none, 5 fps | before / after | 0 / 0 | 0 / 0 | 3/3 / 3/3 |
| none, 10 fps | before / after | 0 / 0 | 0 / 0 | 3/3 / 3/3 |
| 2.5 fps | before / after | 2 / 1 | 8 / 0 | 1/3 / 2/3 |
| 1.7 fps | before / after | 7 / 3 | 12 / 3 | 0/3 / 2/3 |
| 15% detections dropped, 5 fps | before / after | 1 / 0 | 10 / 1 | 8/15 / 14/15 |
| 30% detections dropped, 5 fps | before / after | 4 / 1 | 23 / 7 | 5/15 / 8/15 |
| 30% detections dropped, 10 fps | before / after | 0 / 0 | 3 / 0 | 12/15 / 15/15 |

Zone visit counts were right in every run of both versions. Dwell at 2.5 fps
improved because people are no longer hidden while standing at the table:
before, one-by-one gave 7.6 s and 4.4 s for visits of about 12 s and 11 s; after,
12.0 s and 11.2 s. At 5 fps the pipeline's dwell is now 0.2 to 0.4 s longer
than in the table above (still within the ±3 s tolerance), because the box used
is the detection itself rather than the smoothed track box.

The only remaining error on clean clips: at 2.5 fps face-demographics-walking
gives 8 visitors for 7 (people walking straight at the camera grow faster than
the stitcher allows). Default speed (5 fps) is unchanged at about 3.5x realtime.

Reproduce the end-to-end checks:

```bash
python -m app.cv.evaluate eval/public_clips.json --media-dir DIR --fps 2.5
python -m app.cv.evaluate eval/public_clips.json --media-dir DIR --drop-rate 0.3 --seed 1
```

### Larger detector

YOLO11s vs YOLO11n on 36 evenly spaced frames (confidence 0.35): store-aisle 40
vs 39 people found, other clips identical, no false boxes from either. The one
extra was a man cut off at the frame edge. Running YOLO11n at 960 px found the
same total but swapped a real person for a duplicate box, so it is not an
improvement. YOLO11s costs about 1.9x the detector time on CPU. Through the
stress table above it did not do better than YOLO11n. YOLO11n stays the
default; for crowded stores with CPU to spare, set `YOLO_MODEL=yolo11s.pt` and
compare on that store's clips before switching.

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
* Larger models on store footage. On the public clips `yolo11s` found one more
  partly visible person in 36 frames at about 1.9x the CPU cost (see above).
* Night, IR, rain, glare and very crowded scenes.
