# Implementation plan and status

Phases from the rescue brief, with what was delivered. Evidence for each item is
in `BUILD_SUMMARY.md`.

| Phase | Scope | Status |
|---|---|---|
| P0 Safety and baseline | Audit, issue register, branch, docs | Done (`PROJECT_AUDIT.md`) |
| P1 Repair | Backend, database migrations, analytics bugs, real-data dashboard | Done |
| P2 Computer vision | ByteTrack, behaviour-based events, entry lines, queue outcomes, validation | Done on public clips; store footage pending |
| P3 Durable processing | Postgres job queue, worker, retries, cancel, reprocess, retention | Done |
| P4 Deployment and mobile | Docker, Railway, Vercel, Neon, R2, Codespaces, auth, mobile layout | Config done; cloud deploy blocked on accounts |
| P5 Metrics integrity | One metrics module, definitions, source labels, rule-based anomalies and insights, no demographics | Done (`METRICS.md`) |
| P6 Tests and CI | Backend tests on SQLite and Postgres, frontend checks, image builds | Done (67 tests; CI green) |
| P7 Observability | Liveness/readiness, structured logs, request ids, request metrics, worker heartbeats | Done |

## Next steps, in order

1. **Deploy** (owner's accounts needed): Neon, R2, Railway API + worker, Vercel.
   About 30 minutes following `DEPLOYMENT.md`.
2. **Validate on store footage**: upload the 8 store clips, draw zones and entry
   lines, hand-count a sample, run `app.cv.evaluate` with a private ground-truth
   file. Tune `ANALYSIS_FPS` if entrance tracks split.
3. **Merge** the rescue PR after review; Vercel and Railway then deploy from `main`.
4. Later: a user management page (today it is CLI/API only), live RTSP camera
   ingestion, a larger model option for crowded scenes, IDF1 measurement with
   per-frame annotations.
