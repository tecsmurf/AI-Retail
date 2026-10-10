# Build summary: PurpleSol v2 rescue

Branch `claude/purplesol-rescue-j7olbe`, pull request #2. Not merged, not deployed.

## In one paragraph

PurpleSol on `main` was a demo: the dashboard showed invented numbers, the API
could not compute real revenue or historic footfall, the backend image did not
build, there was no login, and the CV logic counted every new track as a
customer entry and every billing-camera sighting as a purchase. v2 replaces
this with a working pipeline: upload CCTV video from a phone, a background
worker detects and tracks people (anonymously), turns their movement into
entries, zone visits, dwell and queue events, and the dashboard reports metrics
from those events and the POS data, with every number labelled with its source
and definition. On public test clips it counted all 20 people correctly. It has
not been run on the store's own footage or deployed to the cloud yet.

## Root causes (detail in `PROJECT_AUDIT.md`)

1. The frontend was built against mock data and never wired to the API.
2. Analytics assumed UTC "today" and matched POS rows on the wrong key.
3. CV events were inferred from which camera saw someone, not from movement.
4. Inference ran inside the API request and wrote to a local file.
5. An unbuildable dependency pin and no CI meant nothing was ever run end to end.

## Checklist

| Item | Result | Evidence |
|---|---|---|
| Backend image builds | PASS | CI run 38049150378, job `docker` |
| Worker image builds and loads YOLO | PASS | same job, step "Worker image can load the model" |
| Database migrations (fresh, v1 upgrade, downgrade) | PASS | `tests/test_seed_migrations.py`; SQLite and Postgres in CI |
| Backend tests | PASS | 67 passed locally and in CI on SQLite and Postgres |
| Frontend lint, typecheck, production build | PASS | CI job `frontend` |
| Auth: login, roles, CSRF, rate limits, secure cookie, sign out everywhere | PASS | `tests/test_api.py` |
| Upload → job → worker → events → analytics | PASS | `tests/test_jobs_worker.py`; also run by hand on a local stack with 3 public clips |
| Job retry, cancel, stale requeue, shutdown handover | PASS | `tests/test_jobs_worker.py` |
| Revenue from POS, local-day footfall | PASS | `tests/test_api.py` |
| No mock data on any page | PASS | `demo-data.ts` deleted; pages read the API only |
| Mobile layout (390 px) | PASS | Playwright screenshots during the build; no horizontal scroll |
| CV detection on public clips | PASS | precision 1.00, recall 0.95 on 58 people (`CV_VALIDATION.md`) |
| CV counting on public clips | PASS | 7 of 7 checks (`python -m app.cv.evaluate`) |
| CV on the store's own CCTV | BLOCKED | the owner's PC with the clips was offline |
| Ground truth checked by a human | NOT DONE | counts were made by the AI agent |
| IDF1 / MOTA | NOT DONE | needs per-frame identity annotations |
| Cloud deployment (Railway, Neon, R2, Vercel) | BLOCKED | no credentials; an existing Vercel project `ai-retail` was found but the connector is not authorised for that team |
| Codespaces | NOT TESTED | config present, never opened in a real Codespace |
| Railway config keys | CHECKED | `preDeployCommand`, `drainingSeconds`, `overlapSeconds` exist in Railway's published schema; not exercised on Railway |

## Architecture

See the diagram in `DEPLOYMENT.md`. In short: Next.js on Vercel proxies `/api`
to a FastAPI service; a separate worker claims jobs from Postgres, reads videos
from S3/R2, runs YOLO11n + ByteTrack, and writes events; everything is in one
Postgres database.

## What changed (117 files)

* **Backend**: new `api/` (auth, system, pos, videos), `services/` (metrics,
  ingest, jobs, POS, insights, time ranges), `cv/` (video IO, geometry, event
  engine, evaluate), `worker.py`, `storage.py`, `security.py`, `migrate.py`,
  `cli.py`, Alembic migrations, 5 test modules. Removed the websocket, the
  in-request video endpoint and the old services.
* **Frontend**: every page rewritten on the API; new Login, Videos, Cameras &
  zones (zone editor), System; mock data and fake pages removed.
* **Infra**: two Dockerfiles, two Railway configs, docker-compose, devcontainer,
  Makefile, GitHub Actions.
* **Docs**: this folder (`PROJECT_AUDIT`, `IMPLEMENTATION_PLAN`, `BUILD_LOG`,
  `DECISIONS`, `DEPLOYMENT`, `CV_VALIDATION`, `REMOTE_ACCESS`, `METRICS`).

## What the owner needs to do

1. Create Neon, Cloudflare R2, Railway and Vercel accounts or projects and
   follow `DEPLOYMENT.md` (or give Claude access to them).
2. Make the 8 CCTV clips available (keep the PC on with the Claude desktop app
   open, or upload them through the deployed app) so they can be validated.
3. Review and merge pull request #2.

## Risks

* Accuracy on real store cameras is unknown until step 2. Crowds, occlusion,
  low resolution and fisheye lenses will lower recall.
* Fast walkers at 5 fps can get two track ids (see D6 in `DECISIONS.md`).
* Entry counts depend on drawing the entry line where people's feet cross it.
* CPU processing at about 3 to 4x real time means a full day of one camera takes
  hours. Add workers or a GPU if footage volume grows.
* The login rate limiter is per process and resets on restart.
