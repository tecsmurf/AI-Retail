# Event Schema Reference

## Event Types

| Type | Trigger | Key Fields |
|------|---------|-----------|
| ENTRY | New person detected at entrance | customer_id, camera_id, gender, age |
| EXIT | Person leaves store | customer_id, camera_id |
| ZONE_ENTER | Person enters a business zone | customer_id, zone_name, zone_type |
| ZONE_EXIT | Person leaves a business zone | customer_id, zone_name, dwell_seconds |
| DWELL_TIME | Computed zone stay duration | customer_id, zone_name, dwell_seconds |
| CHECKOUT | Person completes purchase | customer_id, zone_name |
| QUEUE_ENTER | Person joins queue | customer_id, queue_position |
| QUEUE_EXIT | Person leaves queue | customer_id, queue_wait_seconds |
| QUEUE_COMPLETED | Person served at counter | customer_id, queue_wait_seconds |
| QUEUE_ABANDONED | Person leaves without being served | customer_id, queue_wait_seconds |

## Sample Event Formats (from provided data)

### Entry/Exit Format
```json
{"event_type":"entry","id_token":"ID_60001","store_code":"store_1076","camera_id":"cam1","event_timestamp":"2026-03-08T18:10:05.120000","is_staff":false,"gender_pred":"F","age_pred":28,"age_bucket":"25-34"}
```

### Zone Format
```json
{"event_type":"zone_entered","track_id":101,"store_id":"ST1076","camera_id":"CAM2","zone_id":"PURPLLE_MUM_1076_Z01","zone_name":"Left Shelf","zone_type":"SHELF","is_revenue_zone":"Yes","event_time":"2026-03-08T18:10:45.280000"}
```

### Queue Format
```json
{"event_type":"queue_completed","track_id":102,"store_id":"ST1076","queue_join_ts":"2026-03-08T18:13:05.080000","queue_served_ts":"2026-03-08T18:13:13.240000","queue_exit_ts":"2026-03-08T18:15:31.840000","wait_seconds":8,"queue_position_at_join":2,"abandoned":false}
```
