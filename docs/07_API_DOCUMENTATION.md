# API Documentation

## Base URL
- Development: `http://localhost:8000`
- Production: `https://purplesol-api.railway.app`

## Authentication
Currently open (hackathon MVP). Production would use JWT/API keys.

## Endpoints

### Health
| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Basic health check |
| GET | `/health` | Detailed health |

### Stores
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/stores` | List all stores |
| GET | `/api/stores/{id}` | Store overview with metrics |
| GET | `/api/stores/{id}/cameras` | List cameras |
| GET | `/api/stores/{id}/zones` | List zones |

### Events
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/events` | Ingest single event |
| POST | `/api/events/batch` | Batch ingest events |
| GET | `/api/events` | Query events (filterable) |
| GET | `/api/events/customer/{id}` | Customer events |

### Analytics
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/analytics/{store_id}` | Full analytics |
| GET | `/api/analytics/{store_id}/footfall` | Footfall metrics |
| GET | `/api/analytics/{store_id}/zones` | Zone analytics |
| GET | `/api/analytics/{store_id}/conversion` | Conversion funnel |
| GET | `/api/analytics/{store_id}/queue` | Queue analytics |
| GET | `/api/analytics/{store_id}/demographics` | Demographics |
| GET | `/api/analytics/{store_id}/revenue` | Revenue metrics |
| GET | `/api/analytics/{store_id}/journeys` | Customer journeys |
| GET | `/api/analytics/{store_id}/journeys/analytics` | Journey summary |
| GET | `/api/analytics/{store_id}/journeys/top-paths` | Top paths |
| GET | `/api/analytics/{store_id}/anomalies` | Anomalies |
| GET | `/api/analytics/{store_id}/alerts` | Alerts |
| POST | `/api/analytics/{store_id}/detect-anomalies` | Trigger detection |

### WebSocket
| Protocol | Path | Description |
|----------|------|-------------|
| WS | `/ws` | Global updates |
| WS | `/ws/store/{id}` | Store-specific updates |

## Interactive Docs
FastAPI auto-generates OpenAPI docs at `/docs` (Swagger) and `/redoc`.
