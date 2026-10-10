# Metrics

Every number on the dashboard comes from `backend/app/services/metrics.py`.
The live definitions are served at `GET /api/analytics/definitions`, and each
analytics response says which date range, store time zone and data sources it
used. Staff tracks (`is_staff`) are excluded everywhere.

| Metric | Definition | Confidence |
|---|---|---|
| Entries | ENTRY events: a track crossed a camera's entry line inward and stayed inside for the confirmation window. Someone entering twice counts twice. | Measured. Depends on the line being drawn where feet cross it (`CV_VALIDATION.md`). |
| Exits | EXIT events: line crossings outward. | Measured. |
| Zone visits | Completed visits (ZONE_EXIT). A visit starts once the ground point stays in the zone for the enter threshold and ends once it stays out for the exit grace period. | Measured. |
| Dwell time | Seconds between a visit's ZONE_ENTER and ZONE_EXIT. | Measured; about ±1 s on the public clips. |
| Queue wait | Seconds a track spent in a QUEUE zone. | Measured. |
| Queue completed | After the queue, the same track reached a BILLING zone within the link window. | Observed. |
| Queue abandoned | The track left the queue, stayed visible and did not reach a counter within the window. Needs a counter zone on the same camera. | Inferred; labelled as such. |
| Queue length | People inside QUEUE zones, sampled every 5 s of processed video. | Measured. |
| Transactions, revenue | Distinct POS order ids and their totals for the store's POS code. | From POS data. |
| Conversion rate | Transactions / entries over the same hours. | Estimate. Unavailable when there is no POS data; never derived from footfall alone. |
| POS match | A POS order linked to a counter visit when the order time falls within the visit (plus grace). One-to-one, nearest in time. | Estimated link, not identification. |

## Anomalies (rule-based, `services/anomaly_service.py`)

| Rule | Fires when |
|---|---|
| LONG_QUEUE_WAIT | At least `min_long_waits` waits over `long_wait_seconds` (default 300 s) in one local hour. |
| QUEUE_BUILDUP | Queue length at or above `buildup_length` for at least `buildup_seconds` of consecutive samples. |
| TRAFFIC_DROP | An hour's entries fall below `drop_ratio` × the mean of the same hour on earlier days. Needs `baseline_min_days` of history, otherwise it reports "insufficient data". |

Each anomaly stores the metric value and threshold that triggered it, and a
dedupe key so re-running detection does not duplicate it.

## Insights (`services/insights.py`)

Deterministic rules over the metrics above. Each insight shows the numbers it is
based on and a confidence from the sample size (for example, at least 30 zone
visits or 50 entries). Below that it says the data is too thin instead of making a
recommendation. No language model is involved.

## Not reported

* Age, gender or any other demographic: no validated model (`/demographics`
  returns `available: false`).
* Unique visitors across days or cameras: tracks are anonymous and per video.
* Purchases inferred from being near the counter.
