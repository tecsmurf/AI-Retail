# Customer Journey Engine

## Journey Reconstruction
Customer journeys are automatically reconstructed from event sequences.

### Process
1. Group events by `customer_id` within a store visit
2. Order events by timestamp
3. Identify entry and exit points
4. Collect zone transitions
5. Calculate total duration and dwell times
6. Classify journey type

### Journey Types
| Type | Criteria |
|------|----------|
| **Conversion** | Visited billing zone / made purchase |
| **Browse** | Visited ≥1 zone, no purchase, duration >60s |
| **Bounce** | No zone visits or duration <60s |
| **Abandonment** | Reached billing queue but abandoned |

### Example Journey
```
ENTRY (18:10:05)
  ↓
Faces Canada (18:10:45 → 18:11:18, dwell: 33s)
  ↓
Mars + NY Bae (18:11:42 → 18:12:20, dwell: 38s)
  ↓
Billing Queue (18:12:58, wait: 15s)
  ↓
EXIT (18:15:31)

Type: CONVERSION | Duration: 5m 26s | Zones: 2
```

## Path Analytics
- **Top Paths**: Most common zone sequences
- **Conversion Paths**: Paths that lead to purchases
- **Abandonment Paths**: Paths ending without purchase
- **Average Journey Duration**: Time from entry to exit
- **Average Zones Visited**: Mean zone count per journey

## POS Correlation
Journeys can be linked to POS transactions by matching:
- Exit time near transaction time
- Same store
- Queue completion event → order correlation
