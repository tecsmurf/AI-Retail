# Deployment

**Status: not deployed.** Everything below has been prepared and the container
images build and start in CI, but no cloud account was connected during the
rescue, so there are no live URLs yet. Follow these steps once, then the app
runs without your laptop.

This replaces `14_DEPLOYMENT_GUIDE.md`, which describes the old demo setup.

## What runs where

```
Phone / laptop browser
        │  https://<your-app>.vercel.app
        ▼
Vercel: Next.js dashboard ── /api/* rewrite ──► Railway: API service (FastAPI)
        │                                              │
        │ presigned PUT (video bytes go               ├──► Neon: PostgreSQL
        │ straight to storage)                         │      (data + job queue)
        ▼                                              │
Cloudflare R2 (or any S3) ◄──── Railway: worker service (YOLO + ByteTrack)
```

* **Dashboard (Vercel).** The browser only talks to the Vercel domain. Vercel
  forwards `/api/*` and `/health/*` to the API, so the login cookie is first-party
  and CORS is not involved for normal pages.
* **API (Railway).** Auth, configuration, analytics, upload sessions. It never
  runs the model.
* **Worker (Railway).** Claims jobs from the `processing_jobs` table, downloads the
  video from storage, runs CV, writes events. You can run more than one.
* **Database (Neon).** All data, plus the job queue. There is no Redis.
* **Storage (R2/S3).** Uploaded videos, reference frames, job artifacts.

## Cost and size guidance

| Service | Minimum | Notes |
|---|---|---|
| Vercel | Hobby | Static pages plus rewrites. |
| Railway API | 512 MB RAM | No CV libraries in this image. |
| Railway worker | 2 GB RAM, 2+ vCPU | Peak memory was 660 MB in tests. At 5 fps it processed 3 to 4x faster than real time on 4 CPU cores (see `CV_VALIDATION.md`). Fewer cores means slower. |
| Neon | Free tier | Use the **direct** connection string (not `-pooler`). |
| R2 | Free tier | 10 GB free storage. Videos are kept for `VIDEO_RETENTION_DAYS`. |

## Step by step

### 1. Database (Neon)

1. Create a project at neon.tech, region close to Railway's.
2. Copy the **direct** connection string, for example
   `postgresql://user:pass@ep-xxx.region.aws.neon.tech/neondb?sslmode=require`.
   The app converts it for asyncpg and turns on TLS itself. Do not use the
   pooled (`-pooler`) host: asyncpg's prepared statements do not work through
   PgBouncer in transaction mode.

### 2. Storage (Cloudflare R2)

1. Create a bucket, for example `purplesol-media`. Keep it private.
2. Create an API token with Object Read & Write on that bucket. Note the access
   key id, secret, and the S3 endpoint `https://<account-id>.r2.cloudflarestorage.com`.
3. Add a CORS policy so the browser can upload straight to the bucket:

```json
[
  {
    "AllowedOrigins": ["https://<your-app>.vercel.app"],
    "AllowedMethods": ["PUT", "GET"],
    "AllowedHeaders": ["Content-Type"],
    "ExposeHeaders": ["ETag"],
    "MaxAgeSeconds": 3600
  }
]
```

Without this rule, uploads fail in the browser with a CORS error while
everything else works.

### 3. API and worker (Railway)

Create one Railway project with two services from the GitHub repo.

**API service**

* Root directory: `backend`. Config-as-code path: `backend/railway.toml`.
* It builds `backend/Dockerfile`, runs `python -m app.migrate` before each deploy,
  and only goes live when `/health/ready` returns 200 (database reachable, schema
  up to date, storage usable).
* Generate a public domain under Settings > Networking.

**Worker service**

* Same repo, root directory `backend`, config path `backend/railway.worker.toml`.
* It builds `backend/Dockerfile.worker` (CPU PyTorch, ffmpeg, bundled `yolo11n.pt`).
* No public domain needed. On redeploy it gets 60 s after SIGTERM to hand its
  current job back to the queue.

**Variables for both services** (use Railway's shared variables):

| Variable | Value |
|---|---|
| `APP_ENV` | `production` |
| `SECRET_KEY` | 48+ random characters: `python -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `DATABASE_URL` | the Neon direct string |
| `STORAGE_BACKEND` | `s3` |
| `S3_BUCKET` | `purplesol-media` |
| `S3_ENDPOINT_URL` | `https://<account-id>.r2.cloudflarestorage.com` |
| `S3_REGION` | `auto` |
| `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY` | from the R2 token |

**API only**

| Variable | Value |
|---|---|
| `API_CORS_ORIGINS` | `https://<your-app>.vercel.app` (comma-separate more) |
| `ADMIN_EMAIL`, `ADMIN_PASSWORD` | first admin; only used while there are no users. Remove `ADMIN_PASSWORD` after the first login. |
| `INGEST_API_KEY` | optional, only for pushing events from another system |

**Worker only (optional)**: `ANALYSIS_FPS` (default 5), `YOLO_MODEL`,
`CV_DEVICE`, `JOB_MAX_ATTEMPTS`.

In production the API refuses to start, with a clear log message, if
`SECRET_KEY` is weak, the database is SQLite, storage is local (unless
`ALLOW_LOCAL_STORAGE=true` on a single host), or CORS contains `*`.

### 4. Dashboard (Vercel)

1. Import the repo, root directory `frontend`, framework Next.js.
2. Add the environment variable `API_ORIGIN=https://<api>.up.railway.app`.
   It is read at **build** time, so redeploy after changing it.
3. Deploy. Then put the Vercel URL in the API's `API_CORS_ORIGINS` and in the
   R2 CORS rule.

### 5. Check it

1. `https://<api>.up.railway.app/health/ready` returns `"status": "ready"`.
2. Open the Vercel URL on your phone, sign in with the admin account.
3. **System** page: the worker is listed as online with the model loaded.
4. **Cameras & zones**: create a store and camera, upload a reference frame, draw zones.
5. **Videos**: upload a short clip, watch the job go queued → running → completed.
6. **Overview**: switch the date range to the recording date.

### Optional: load the sample data

The sample files live in the repo's `purple/` folder, which is not inside the
API image, so run the seed from a checkout (a Codespace works) against the Neon
database:

```bash
cd backend
DATABASE_URL='<neon direct string>' python -m app.seed --sample   # marked source=sample
```

Sample data is hidden unless the dashboard's data toggle is set to **All**.

## Local / single machine

```bash
docker compose up --build              # Postgres, migrations, API :8000, worker
docker compose --profile s3 up         # adds MinIO to test the S3 path
cd frontend && npm ci && npm run dev   # dashboard :3000
```

## Operations

* **Migrations** run automatically before each API deploy. Run them by hand with
  `python -m app.migrate`. Back up Neon (branch or dump) before a schema change.
* **New user / reset password**: `python -m app.cli create-user EMAIL --role viewer`
  or `python -m app.cli reset-password EMAIL` from a Railway shell. A reset signs
  the user out everywhere.
* **Stuck job**: a job whose worker stops heartbeating is requeued after
  `JOB_STALE_AFTER_SECONDS` (180 s) and fails after `JOB_MAX_ATTEMPTS` (3). Cancel
  or retry it on the Videos page.
* **Monitoring**: point an uptime monitor at `/health/ready`. Request counts and
  latency are at `/api/system/metrics` (admin).
* **Scaling**: add worker replicas; jobs are claimed atomically, so two workers
  never process the same job.
