# Decisions (v2 rescue)

Engineering decisions made during the October 2026 rescue, without asking for
approval each time, as requested. Earlier records are in `16_DECISIONS.md`;
where they disagree, this file wins.

Format: decision, why, what it costs, how to undo.

## D1. Postgres is the job queue; Redis is dropped

* **Why:** one fewer service to pay for and keep running. Video jobs are minutes
  long and few, so the queue sees a handful of operations per minute.
  `processing_jobs` uses an atomic conditional `UPDATE` to claim a job, heartbeats,
  stale-job requeue and bounded attempts. It works on SQLite for tests and
  Postgres in production.
* **Cost:** no pub/sub; the dashboard polls job status every few seconds.
* **Undo:** `job_service` is the only module that touches the queue.

## D2. The API never runs the model

* **Why:** the old upload endpoint ran inference inside the HTTP request, so one
  long video blocked the API and a redeploy lost the work. Now the API stores the
  file and creates a job; a separate worker process does CV.
* **Cost:** two Railway services instead of one. The API image no longer contains
  PyTorch, which makes it smaller and faster to deploy.

## D3. Uploads go straight to object storage

* **Why:** videos are hundreds of MB. With S3/R2 the browser gets a presigned
  `PUT` URL, so the bytes never pass through the API. Local storage is kept for
  development and single-host Docker setups only.
* **Cost:** the bucket needs a CORS rule (see `DEPLOYMENT.md`).

## D4. YOLO11n + supervision ByteTrack; the custom tracker is retired

* **Why:** the old IoU tracker dropped a person after one missed frame, so one
  shopper became several. ByteTrack keeps tracks through short misses. A test
  (`tests/test_cv_logic.py`) shows the old tracker fragmenting where ByteTrack
  does not. The old code stays in `cv/legacy_tracker.py` for that comparison.
* **Cost:** ByteTrack still loses identity on large jumps between analysed frames
  (see D6).

## D5. Events come from behaviour, not from which camera saw someone

* ENTRY/EXIT need a drawn entry line and a confirmed crossing in a direction,
  instead of "every new track on the entrance camera is an entry".
* Zone visits need the person's ground point (bottom centre of the box) inside the
  polygon for a minimum time; short flickers are ignored.
* A queue visit is "completed" only when the same track is then seen in a counter
  zone, and "abandoned" only when it stays visible and does not reach one. Being
  seen by the billing camera is no longer counted as a purchase.

## D6. Analyse at 5 fps by default; matching threshold stays 0.8

* **Why:** 5 fps processed 3 to 4x faster than real time on 4 CPU cores and counted
  all 20 people correctly on the public clips (`CV_VALIDATION.md`). 10 fps gave
  the same counts at half the speed.
* **Risk:** in synthetic tests a person moving more than about half a box width
  between analysed frames gets a new track id. If store entrance footage shows
  duplicate visitors, set `ANALYSIS_FPS=10` on the worker first, then consider a
  matching threshold of 0.9.

## D7. No demographics

* The old code had gender and age fields filled from nowhere. There is no
  validated, privacy-reviewed model for this, so the API returns
  `available: false` and the sample importer drops those fields. Tracks stay
  anonymous numbers; no faces are stored or recognised.

## D8. Every event records its source

* `source` is one of `cv` (worker), `api` (ingest key), `sample`, `demo` or
  `legacy_cv` (v1 data). The dashboard shows **Real** data (cv + api) by default
  and only includes the rest when you switch to **All**, so sample numbers can never
  be mistaken for store numbers.
* Events have a deterministic `event_key` with a unique index, so re-importing or
  reprocessing never double counts. Reprocessing a video replaces its earlier
  results.

## D9. Time zones: store everything in UTC, report in store-local time

* Each store has an IANA time zone (default `Asia/Kolkata`). "Today", hourly
  charts and day ranges are in that zone. The old code used UTC "today", which hid
  most of the Indian business day.

## D10. One metrics module

* `services/metrics.py` computes every number the dashboard shows, and
  `GET /api/analytics/definitions` returns the definition of each one. Insights
  and anomalies are built from the same functions, so the Overview, Analytics and
  Insights pages cannot disagree. See `METRICS.md`.

## D11. Conversion needs POS data

* Conversion is POS transactions divided by entries for the same hours, and is
  labelled an estimate. With no POS data it is shown as unavailable instead of
  being derived from footfall. A POS order is linked to a counter visit only by
  time overlap and is described as an estimated link.

## D12. Cookie sessions behind a same-origin proxy

* The dashboard calls `/api` on its own domain and Vercel forwards it to Railway.
  The session is an httpOnly, Secure, SameSite=Lax cookie, so scripts cannot read
  it and third-party cookie blocking does not apply. Cookie-authenticated writes
  also need the `X-PurpleSol-CSRF` header. Passwords use scrypt. Roles: admin
  and viewer. Login and upload are rate limited in process (per replica).
* **Cost:** the rate limiter resets on restart and is per replica. Good enough
  for a few users; move it to Postgres if there are many API replicas.

## D13. Alembic migrations with an adopted baseline

* Revision `0001` matches the v1 schema exactly, so an existing v1 database is
  stamped and upgraded in place with its rows kept. `0002` adds v2 tables and
  columns. The API deploy runs migrations first and `/health/ready` fails if the
  schema is behind. `DB_AUTO_CREATE` exists only for throwaway setups.

## D14. Dependencies pinned to versions that install on Python 3.11

* `lap` 0.4.0 does not build on Python 3.11 and broke the image; it is now 0.5.12.
  `numpy` is pinned to 1.26.4 for the OpenCV and PyTorch builds used.
  PyTorch comes from the CPU wheel index, so the worker image does not download
  CUDA. No other upgrades were made.

## D15. Demo-only pages removed

* The Live page invented events every few seconds and the Heatmap page drew
  random numbers. Both are removed and their URLs redirect to Videos and
  Analytics. A live view can come back once there is a real stream to show.

## D16. Validation clips and ground truth

* Public Intel sample clips were used because the store's own clips were not
  reachable. The ground truth was made by the AI agent, not a person, and says so.
  Footage is never committed; `eval/public_clips.json` holds only counts and
  camera layouts.

## D17. Tracking robustness changes (pipeline 2.1)

* Tracks are taken from ByteTrack's own detection association instead of
  supervision's IoU > 0.5 re-match, which hid people for seconds. Tracks are
  reported from the first frame, short tracks must also last 0.5 s, fragments
  are stitched for up to 2 s, and a crossing followed by loss of the track
  counts. Each was kept only if it did not make any clean or stressed run on the
  public clips worse; numbers are in docs/CV_VALIDATION.md.
* YOLO11n stays the default detector. YOLO11s was only marginally better on the
  public clips at about twice the CPU cost.
* The evaluator gained `--drop-rate`/`--seed` so a change can be checked against
  missed detections without new footage.

# Decisions (chain product, November 2026)

Numbering starts at D19 because D18 is used by the website redesign.

## D19. Organisations, regions and four roles

* Every user, store and POS row belongs to one organisation. Stores can sit in
  a region. Roles: HQ admin, HQ viewer (both see every store), regional manager
  and store manager (see only the regions and stores they were given).
* A resource outside the caller's scope answers 404, not 403, so its existence
  is not revealed. Scoping lives in one place (`app/access.py`).
* Existing data moves into a "Default organisation" in migration `0003`, so a
  v2 database upgrades in place. Store codes are unique per organisation.
* Email addresses stay unique across organisations (one login, one
  organisation). **Cost:** a consultant working for two chains needs two emails.
* Every change to people, stores, cameras, videos and boxes writes an audit
  row in the same transaction as the change.
* The ingest API key can target an organisation with the `X-PurpleSol-Org`
  header; without it events go to the default organisation as before.
* Request metrics (`/api/system/metrics`) are for the operator only (admins of
  the default organisation), because they describe the whole service.

## D20. Live cameras through a box in the store, not through the cloud

* **Decision:** a small program on a store PC reads the recorder's streams,
  runs the same tracking code as the video worker and sends events. The cloud
  never connects into the store and never receives video.
* **Why:** store recorders sit behind NAT; opening ports or uploading
  continuous video is what chains refuse. It also keeps recorder passwords out
  of our database: stream addresses live only in the box's `edge.json`.
* A box is paired with a single-use code and then uses a token of which only
  the hash is stored. Replacing or removing a box cuts the old one off at once.
* Live events use their own source (`edge`) and count as real data. Queue
  samples from live streams have no job. Live time is stored as seconds per
  camera and hour, so the dashboard can show how much was actually watched.
* A still image of a camera is sent only when an administrator asks for it, to
  draw zones on. It is the only picture that leaves the store, and the server
  refuses one nobody asked for.
* **Cost:** a PC per store has to run the box, and its CPU limits the number
  of cameras. **Not yet done:** a run against a real recorder.
* **Undo:** remove `edge/`, the `/api/edge*` routes and migration `0004`; video
  upload keeps working without it.

## D21. Privacy defaults and the draft privacy pack

* Annotated frames made while processing a recording are deleted with the
  recording (`VIDEO_RETENTION_DAYS`). They show people; the tracks file holds
  only numbers and is kept.
* IP addresses in the activity log are blanked after `AUDIT_IP_RETENTION_DAYS`
  (default 90). The entries stay.
* A camera's still image can be removed by an admin, is deleted from storage
  at once, and is served with `no-cache` so a removed image does not linger in
  a browser.
* `docs/privacy/` holds drafts for a chain's lawyer and IT team. They describe
  what the code does and list the open legal questions (lawful basis for
  shoppers, children, staff, hosting location). **They are not legal advice.**
* **Not built:** one-step deletion of an organisation, backups, SSO, 2FA.
