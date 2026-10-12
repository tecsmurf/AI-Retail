# Build log (v2 rescue)

Continues `15_BUILD_LOG.md`, which covers the v1 demo build.

## 2026-10-10

### Audit
* Read every backend, CV and frontend file on `main` (dd843f4). Findings in
  `PROJECT_AUDIT.md`.
* Tried building the backend image's dependencies on Python 3.11: `lap==0.4.0`
  fails to build. Pinned 0.5.12.

### Backend and database (commit 09a615d)
* Alembic set up with a baseline that matches the v1 schema, then a v2
  migration (jobs, users, video records, occupancy samples, event provenance,
  store time zones). Tested: fresh upgrade, v1 database upgrade with rows kept,
  downgrade and re-upgrade, on SQLite and Postgres 16.
* New modules: auth and users, storage (local and S3), jobs and worker, metrics,
  time ranges, POS import, insights, ingest.
* CV rebuilt: video reader with metadata checks, YOLO person detector,
  ByteTrack, zone mapper on ground points, event engine with debounce, entry line,
  queue outcomes and occupancy sampling.

### Tests (a560ed9)
* 67 tests: API, auth, CSRF, rate limits, configuration rules, idempotent
  ingestion, local-day analytics, POS revenue, job lifecycle (upload, worker,
  cancel, retry, stale requeue, max attempts, shutdown requeue, exclusive claim),
  video edge cases (empty, corrupt, truncated), synthetic end-to-end queue and
  entry-line scenarios, seed idempotency, model/migration parity.
* Bugs found by the tests and fixed: `from __future__ import annotations` in
  `deps.py` broke FastAPI's query parameter resolution (500 on analytics), a stale
  ORM identity map hid requeued jobs, the worker ignored SIGTERM until the job
  ended.

### Dashboard (e7a5550)
* Removed `demo-data.ts`, the Live and Heatmap pages. Rebuilt Overview,
  Analytics, Journeys, Insights on the API; added Login, Videos (upload and jobs),
  Cameras & zones (with a touch-friendly zone editor) and System.
* Checked at 390 px and 1440 px wide with Playwright screenshots; fixed horizontal
  overflow on the setup page.

### Deployment (83903ff)
* API and worker Dockerfiles, Railway config for each, docker-compose with
  optional MinIO, Codespaces devcontainer, GitHub Actions CI.
* CI run 1 on the PR: backend (SQLite), backend (Postgres), frontend and
  docker jobs all passed, including loading the YOLO model inside the worker image.

### End-to-end run on a local stack
* Postgres, API, worker and dashboard running together. Created a lab store with
  three cameras, uploaded three public sample clips through the API, all three
  jobs completed (3.2x to 4.25x real time), and the dashboard showed the results.

### CV validation (68d057b)
* Detection reviewed on 36 frames: precision 1.00, recall 0.95.
* Counting checked on three clips with `app.cv.evaluate`: all checks pass (6/6
  visitors and entries, 7/7 and 7/7, 7/7 visitors). Details and limits in
  `CV_VALIDATION.md`.
* Found that a badly placed entry line explains the low event count from the
  first lab run; documented.

### Not done
* Validation on the store's own CCTV clips: the owner's PC was offline.
* Cloud deployment: no Railway, Neon, R2 or Vercel credentials were provided.
