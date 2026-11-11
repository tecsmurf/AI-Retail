# End-to-end test report, 11 Nov 2026

Tested: `main` at 390e6b0 (PR #3 merged), on a 4 vCPU cloud machine with no GPU,
Python 3.11, Node 22, PostgreSQL 16. Nothing here was tested on real store
footage or a real camera; see "Not tested".

## Summary

The product works end to end on a local stack with recorded video: a store
owner can sign in, add a store and an entrance camera, draw a zone and an entry
line on a still image, upload a recording, and see correct entries, zone visits,
dwell, journeys, revenue and conversion on the dashboard. One problem was found
and fixed in this branch (the vision library sent usage analytics to Google).

## Results

| Area | What was run | Result |
|---|---|---|
| Backend lint | `ruff check app tests` | Pass |
| Backend tests, SQLite | `pytest -q` | 80 of 80 pass (81 with the new test) |
| Backend tests, PostgreSQL 16 | `TEST_DATABASE_URL=... pytest -q` | 80 of 80 pass |
| Migrations | `python -m app.migrate` on an empty Postgres | Reaches revision 0002; `/health` reports database and storage ok |
| Frontend | `npm run lint`, `tsc --noEmit`, `npm run build` | All pass, 9 routes built |
| CI on `main` | GitHub Actions run 42785041904 | Green (includes both Docker image builds) |
| Vision accuracy | `python -m app.cv.evaluate eval/public_clips.json` | 3 of 3 clips pass (see below) |
| Browser walk-through | Playwright, real API, real worker, Postgres | Works (see below) |

### Vision pipeline on public clips

Same Intel sample clips and agent-made ground truth as docs/CV_VALIDATION.md
(not human-checked, not store footage).

| Clip | Visitors | Entries | Zone visits | Speed |
|---|---|---|---|---|
| one-by-one | 6 of 6 | 6 of 6 | 6 of 6, dwell within 3 s | 3.5x realtime |
| people-detection | 7 of 7 | 7 of 7 | n/a | 4.0x realtime |
| face-demographics-walking | 7 of 7 | n/a | n/a | 4.3x realtime |

Peak memory about 0.9 GB per worker. Total run 67 s for about 4.5 minutes of video.

### Browser walk-through (as a store owner)

1. Sign in with the admin account: works.
2. Cameras & zones: add store "Test Shop Mumbai" (Asia/Kolkata), add entrance
   camera CAM1, upload a still image, draw an entry line and a "Table" display
   zone, save. The saved configuration read back from the API matched what was
   drawn.
3. Videos: upload the 2 min 19 s one-by-one clip with a start time. The job
   finished in 41 s with 6 tracks and 18 events.
4. Overview, Analytics, Journeys: 6 entries, 6 zone visits, median dwell 16 s,
   all at 4 PM store time (the recording start converted correctly from UTC to
   IST). Every number carries a source label ("CV (processed video): 18").
5. POS: set the POS store code, import a 3-line CSV for the same hour. Revenue
   showed Rs 451 (250 + 120.50 + 80) and conversion 50% (3 transactions / 6
   entries). Both correct.
6. Insights correctly says there is not enough data (needs 50 entries).
7. Phone width (390 px): Overview, Videos and Setup fit with no sideways scroll.

## Problems found

1. **Fixed here: usage analytics sent to Google.** Ultralytics (the YOLO
   library) posts anonymous usage events to google-analytics.com by default.
   That contradicts the privacy pitch to stores (nothing leaves the worker but
   what the API needs). `disable_ultralytics_telemetry()` in
   `app/cv/detector.py` now switches it off before the model loads. Checked by
   forcing the setting on, restarting the worker and processing a video: no
   further calls to google-analytics.com. No footage or counts were in those
   events, but a store's IT team would see the traffic.
2. **Not on `main`: the chain-product work and the Footrail name.** The app on
   `main` still says "PurpleSol". The rebrand, sign-up, multi-store roles, edge
   box for live RTSP cameras, reports and privacy changes were built in October
   on local branches that were never pushed, and are not on GitHub. The website
   redesign (PR #4) is separate.
3. **Minor:** each page logs one 401 in the browser console while the session
   check runs on the sign-in page. Harmless.

## Not tested

* Real store footage or a Hikvision camera. The 8 CCTV clips were not found in
  the folder shared from the owner's PC.
* Live camera feeds: `main` has no RTSP/NVR input; only uploaded recordings.
* Billing-camera queue metrics with real video (covered only by unit tests).
* Hosted deployment (no Neon, R2, Railway or Vercel accounts yet), S3 uploads.
* Docker images locally (this machine's network blocked pip inside Docker); CI
  builds them successfully.

## Testing with a Hikvision camera before live support exists

Record a clip from the NVR or camera and upload it:

* From the NVR: Playback, pick the camera and time, Export to a USB stick
  (choose MP4 if offered), or use the iVMS-4200 app's Download.
* Or record straight from the camera's RTSP stream on a PC on the shop network:
  `ffmpeg -rtsp_transport tcp -i "rtsp://USER:PASS@NVR_IP:554/Streaming/Channels/101" -t 900 -c copy shop.mp4`
  (channel 1 main stream is `101`, sub stream `102`; camera 2 is `201`).

Ten to fifteen minutes from the entrance camera during a busy hour, with a hand
count of people entering, is enough for a first accuracy check.
