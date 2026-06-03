# Database Schema

## Tables

### stores
| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| store_code | VARCHAR(50) | Unique store identifier |
| name | VARCHAR(200) | Display name |
| address | TEXT | Physical address |
| city | VARCHAR(100) | City |
| layout_image_url | TEXT | Store layout image |
| is_active | BOOLEAN | Active flag |

### cameras
| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| store_id | UUID FK | Parent store |
| camera_code | VARCHAR(50) | Camera identifier |
| name | VARCHAR(200) | Display name |
| camera_type | VARCHAR(50) | entrance/zone/billing |

### zones
| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| store_id | UUID FK | Parent store |
| zone_code | VARCHAR(100) | Zone identifier |
| name | VARCHAR(200) | Display name |
| zone_type | VARCHAR(50) | SHELF/DISPLAY/BILLING/ENTRANCE |
| is_revenue_zone | BOOLEAN | Revenue-generating zone |
| polygon_points | JSON | Boundary polygon |
| color | VARCHAR(20) | Heatmap color |

### events
| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| store_id | UUID FK | Parent store |
| event_type | VARCHAR(50) | Business event type |
| customer_id | VARCHAR(100) | Tracked person ID |
| timestamp | TIMESTAMP | Event time |
| zone_name | VARCHAR(200) | Zone name |
| gender | VARCHAR(10) | Predicted gender |
| age | INTEGER | Predicted age |
| dwell_seconds | FLOAT | Dwell time |
| queue_wait_seconds | FLOAT | Queue wait |

**Indexes**: (store_id, timestamp), (store_id, event_type), (store_id, customer_id, timestamp)

### customer_journeys
| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| store_id | UUID FK | Parent store |
| customer_id | VARCHAR(100) | Customer |
| entry_time | TIMESTAMP | Entry time |
| exit_time | TIMESTAMP | Exit time |
| duration_seconds | FLOAT | Total duration |
| zones_visited | JSON | Zone list |
| journey_type | VARCHAR(50) | conversion/browse/bounce |
| made_purchase | BOOLEAN | Purchased flag |

### pos_transactions
| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| order_id | INTEGER | POS order ID |
| store_id | VARCHAR(50) | Store code |
| order_date | DATE | Transaction date |
| brand_name | VARCHAR(200) | Product brand |
| total_amount | FLOAT | Amount |

### anomalies / alerts
Anomaly detection results and real-time alerts.
