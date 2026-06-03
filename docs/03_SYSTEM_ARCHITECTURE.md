# System Architecture

## Overview

PurpleSol uses a modular, event-driven architecture designed for simplicity and scalability.

```
┌──────────────────┐
│  Video Sources   │  CCTV streams / uploaded video files
└────────┬─────────┘
         ↓
┌──────────────────┐
│  FastAPI Backend  │  Python 3.11, async, structured logging
│  ┌──────────────┐│
│  │ CV Pipeline  ││  YOLO11 detection → ByteTrack tracking
│  │ Zone Mapper  ││  Point-in-polygon zone classification
│  │ Event Engine ││  Detection → Business Event conversion
│  └──────────────┘│
└────────┬─────────┘
         ↓
┌──────────────────┐
│   PostgreSQL     │  Events, Journeys, POS, Anomalies
│   (Neon)         │  
└────────┬─────────┘
         ↓
┌──────────────────┐
│   Redis          │  Cache, pub/sub for real-time
│   (Upstash)      │
└────────┬─────────┘
         ↓
┌──────────────────┐
│   WebSocket      │  Real-time event broadcasting
│   Layer          │
└────────┬─────────┘
         ↓
┌──────────────────┐
│   Next.js        │  Dashboard, analytics, monitoring
│   Dashboard      │  Deployed on Vercel
│   (Vercel)       │
└──────────────────┘
```

## Component Details

### Backend (FastAPI)
- **Framework**: FastAPI with async/await
- **ORM**: SQLAlchemy 2.0 (async mode)
- **Validation**: Pydantic v2
- **Logging**: structlog (JSON in production)
- **API Docs**: Auto-generated OpenAPI/Swagger

### Computer Vision
- **Detection**: YOLO11 (person class only)
- **Tracking**: ByteTrack (IoU-based multi-object tracking)
- **Zone Mapping**: Ray-casting point-in-polygon algorithm

### Database
- **Engine**: PostgreSQL 16
- **Cloud**: Neon (serverless PostgreSQL)
- **Indexes**: Composite indexes on (store_id, timestamp), (store_id, event_type)

### Caching
- **Engine**: Redis 7
- **Cloud**: Upstash (serverless Redis)
- **Usage**: Analytics caching, real-time pub/sub

### Frontend
- **Framework**: Next.js 15 (App Router)
- **Styling**: Tailwind CSS v4
- **Charts**: Recharts
- **Icons**: Lucide React
- **State**: React hooks (no external state management needed)

## Data Flow

1. Video frame captured
2. YOLO11 detects persons → bounding boxes
3. ByteTrack assigns persistent IDs → tracks
4. Zone mapper determines which zone each person is in
5. Event engine generates business events (ENTRY, ZONE_ENTER, etc.)
6. Events stored in PostgreSQL
7. Analytics engine computes metrics on demand
8. WebSocket broadcasts real-time updates
9. Dashboard renders visualizations
