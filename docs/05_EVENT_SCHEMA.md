# Event Schema

## Philosophy
PurpleSol is event-driven. Raw CV detections are never stored directly. Every detection is converted into a **business event** with semantic meaning.

## Core Events

### ENTRY
Customer enters the store.
```json
{
  "event_type": "ENTRY",
  "customer_id": "CUST_001",
  "store_code": "store_1076",
  "camera_id": "CAM3",
  "timestamp": "2026-03-08T18:10:05.120000",
  "gender": "F",
  "age": 28,
  "age_bucket": "25-34"
}
```

### EXIT
Customer leaves the store.

### ZONE_ENTER
Customer enters a business zone.
```json
{
  "event_type": "ZONE_ENTER",
  "customer_id": "CUST_001",
  "zone_name": "Faces Canada",
  "zone_type": "SHELF",
  "timestamp": "2026-03-08T18:10:45.280000"
}
```

### ZONE_EXIT
Customer leaves a zone. Includes dwell time.

### DWELL_TIME
Computed dwell time in a zone.

### QUEUE_COMPLETED
Customer completes the billing queue.
```json
{
  "event_type": "QUEUE_COMPLETED",
  "customer_id": "CUST_102",
  "zone_name": "Billing Counter Queue",
  "queue_wait_seconds": 8,
  "queue_position_at_join": 2,
  "abandoned": false
}
```

### QUEUE_ABANDONED
Customer leaves the queue without being served.

## Optional Events (Phase 2)
- `PRODUCT_INTERACTION` — Hand near shelf
- `PRODUCT_PICKUP` — Item lifted
- `PRODUCT_RETURN` — Item put back

## Event Properties

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| event_type | string | ✓ | Event category |
| customer_id | string | ✓ | Tracked person ID |
| store_code | string | ✓ | Store identifier |
| timestamp | datetime | ✓ | Event time |
| camera_id | string | | Source camera |
| zone_name | string | | Business zone name |
| zone_type | string | | SHELF/DISPLAY/BILLING/ENTRANCE |
| gender | string | | M/F prediction |
| age | int | | Age prediction |
| age_bucket | string | | Age range |
| dwell_seconds | float | | Time spent in zone |
| queue_wait_seconds | float | | Queue wait time |
| queue_abandoned | bool | | Left queue early |
| confidence | float | | Detection confidence |
