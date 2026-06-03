# Anomaly Detection

## Detection Types

### LONG_QUEUE
- **Trigger**: ≥3 customers waiting >30 seconds in the last hour
- **Severity**: Medium (30-60s avg) / High (>60s avg)
- **Action**: Alert staff to open additional counters

### ABNORMAL_DWELL
- **Trigger**: Customer stays >5 minutes in a single zone
- **Severity**: Low
- **Action**: May indicate confusion, shoplifting risk, or high engagement

### TRAFFIC_DROP
- **Trigger**: >50% decrease in visitors compared to previous hour
- **Severity**: Medium
- **Action**: Investigate external factors (weather, events, competition)

### EMPTY_STORE (Planned)
- **Trigger**: No visitors for >15 minutes during operating hours
- **Severity**: High
- **Action**: Check if store is accessible, signage issues

### UNUSUAL_MOVEMENT (Planned)
- **Trigger**: Customer revisiting same zone >3 times
- **Severity**: Low
- **Action**: Potential shoplifting indicator

## Alert System
- Anomalies stored in PostgreSQL
- Alerts generated and pushed via WebSocket
- Dashboard shows active/resolved alerts with severity indicators
- Configurable thresholds per store
