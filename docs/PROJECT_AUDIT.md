# Project audit (state of `main` at commit dd843f4, 10 Oct 2026)

This is what the repository looked like before the rescue, and what was done
about each problem. Severity: **critical** = the product cannot work or shows
false numbers; **high** = breaks under real use; **medium** = quality or risk.

## Summary

PurpleSol on `main` was a well-written demo, not a working product. The
dashboard showed hardcoded and random numbers, the API could not produce real
metrics, the backend image could not be built, nothing required a login, and the
computer-vision counts were systematically inflated. None of this was visible
from the README, which described the features as working.

## Dependency map (before)

```
frontend (Next.js) ──► src/lib/demo-data.ts   (all pages; api.ts never called)

backend (FastAPI, no auth)
  ├─ api/video.py ── runs YOLO inside the request ──► data/cv_events.jsonl (local file)
  ├─ api/analytics.py ──► services/analytics_service.py ──► Postgres (create_all, no migrations)
  ├─ api/websocket.py ──► pushes generated events
  └─ config: REDIS_URL (Redis in compose, never used for work)
cv/: detector.py (YOLO) ─► tracker.py (custom IoU) ─► zone_mapper.py ─► analyze_events.py
```

## Issue register

| # | Area | Severity | Problem | Resolution |
|---|---|---|---|---|
| 1 | Build | critical | `lap==0.4.0` does not build on Python 3.11, so the Docker image (and any Railway deploy) failed. | Pinned `lap==0.5.12`; API and worker images now build in CI. |
| 2 | Dashboard | critical | Every page read `demo-data.ts`; `api.ts` was never called. The Live page generated fake events every 2 to 5 s and the Heatmap drew random values. | All pages rebuilt on the real API. Fake pages removed (D15). |
| 3 | Analytics | critical | Footfall counted only "today" in UTC, so historic footage never appeared and most of the Indian day was cut. | Store time zones and explicit date ranges (D9). |
| 4 | Analytics | critical | Revenue filtered POS rows by store UUID, which POS data never contains, so revenue was always ₹0. | POS rows map to stores through `pos_store_code`; unmapped codes are listed. |
| 5 | Analytics | high | Journeys were never built, so the Journeys page could only show mock data. | Journeys built from persisted events (`journey_service`). |
| 6 | CV | critical | The tracker dropped a person after one missed frame, so one shopper became several. | ByteTrack (D4). |
| 7 | CV | critical | Every new track on the entrance camera was counted as an ENTRY. | Direction-aware entry-line crossing (D5). |
| 8 | CV | critical | Anyone seen by the billing camera was counted as a completed purchase. | Queue outcome from observed movement; purchases only from POS (D5, D11). |
| 9 | CV | high | Gender and age fields were present with no model behind them. | Removed (D7). |
| 10 | Processing | high | Upload ran inference inside the HTTP request and appended events to a local JSONL file: a long video blocked the API, a restart lost the work, and events never reached the database. | Durable Postgres job queue and a separate worker (D1, D2). |
| 11 | Security | critical | No authentication on any endpoint, including uploads and event ingestion. | Cookie sessions, roles, CSRF header, rate limits, ingest API key (D12). |
| 12 | Security | high | `SECRET_KEY` defaulted to `dev-secret-key`; CORS allowed all methods and headers with credentials. | Production refuses weak secrets, SQLite, `*` origins; explicit CORS lists. |
| 13 | Health | high | `/health` reported "connected" without touching the database. | `/health/live` and `/health/ready` (DB query, migration head, storage). |
| 14 | Database | high | `create_all` at startup, no migrations. Schema changes would need a reset. | Alembic with a v1 baseline; existing data upgraded in place (D13). |
| 15 | Data | high | Demo, sample and real data were mixed with no way to tell them apart. | `source` on every event; Real/All toggle (D8). |
| 16 | Data | medium | Re-importing events or reprocessing a video double counted. | Deterministic event keys with a unique index. |
| 17 | Infra | medium | Redis was required by compose and config but did no work. | Removed (D1). |
| 18 | Tests | high | Two small test files, partly out of date; no CI. | 67 backend tests on SQLite and Postgres, frontend lint/typecheck/build, Docker builds, in GitHub Actions. |
| 19 | Docs | medium | README and docs described mock features as working. | New docs in this folder; old docs marked as describing v1. |

## Things that were fine and were kept

* Product idea, zone types and store layouts in `docs/context/`.
* The YOLO11n detector choice and the normalized polygon zone format.
* The event schema's basic shape (type, track, zone, timestamp).
* The sample data in `purple/` (events and POS CSV), now imported as `source=sample`.
* The Next.js + Tailwind look of the dashboard.
