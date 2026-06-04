# Build Log

## Day 1 — June 3, 2026

### Phase 1: Foundation (Completed)
- ✅ Repository structure created (monorepo: backend/ + frontend/ + docs/)
- ✅ Backend scaffold: FastAPI with structured logging, CORS, health endpoints
- ✅ Database models: Store, Camera, Zone, Event, CustomerJourney, JourneyEvent, POSTransaction, Anomaly, Alert
- ✅ Pydantic schemas for all entities with validation
- ✅ Service layer: StoreService, EventService, JourneyService, AnalyticsService, AnomalyService
- ✅ API routes: 20+ endpoints covering stores, events, analytics, journeys, anomalies
- ✅ WebSocket layer with global and store-specific broadcasting
- ✅ CV Pipeline: PersonDetector (YOLO11), ByteTracker, ZoneMapper, VideoProcessor
- ✅ Seed script with demo data (300 customer journeys, POS transactions)
- ✅ Frontend: Next.js 15 + Tailwind dark theme dashboard
- ✅ Dashboard features: KPI cards, hourly footfall chart, conversion funnel, zone table, journey paths, anomaly center, demographics, revenue, multi-store comparison
- ✅ Docker setup: Dockerfile + docker-compose.yml
- ✅ Documentation: 21 docs files + 6 context files
- ✅ Virtual environment created with all dependencies installed

### Phase 2: Live CCTV Processing (Completed)
- ✅ Installed YOLO11 + OpenCV + Supervision + LAP dependencies
- ✅ YOLO11n model auto-downloaded (5.4MB)
- ✅ Built `process_videos.py` — full CCTV processing script
- ✅ Configured per-camera zone polygons for both stores
- ✅ **Processed all 8 CCTV videos** (4 per store)
- ✅ **Generated 494 real business events from actual footage**
  - 110 ENTRY events
  - 108 EXIT events
  - 58 ZONE_ENTER events
  - 105 ZONE_EXIT events
  - 47 QUEUE_ENTER events
  - 66 QUEUE_COMPLETED events
- ✅ Per-store results:
  - **Store 1076**: 42 entries, 19 billing completions, 45.2% conversion, 71 unique tracks
  - **Store 1077**: 68 entries, 47 billing completions, 69.1% conversion, 117 unique tracks
- ✅ Average processing speed: ~8 frames/sec on CPU
- ✅ Events saved to `backend/data/cv_events.jsonl`
- ✅ Dashboard updated with "CV Pipeline Results" section showing real metrics
- ✅ Event analysis script created (`analyze_events.py`)

### Architecture Decisions Made
- PostgreSQL over MongoDB (SQL better for analytics queries)
- ByteTrack over DeepSORT (simpler, no re-ID model needed)
- Demo data approach for immediate dashboard rendering
- Event-driven design from day 1
- YOLO11n for speed/accuracy tradeoff on CPU
- Process every 15th frame for speed (still captures all movements)

### Key Technical Achievements
- Full YOLO11 → ByteTrack → Zone Mapping → Event Generation pipeline
- Real person detection at 0.4 confidence threshold
- Queue wait time estimation from track persistence
- Zone transition detection via position → polygon mapping
- 494 real events from 8 CCTV clips processed in ~195 seconds

### Next Steps (Remaining)
- [ ] Push to GitHub (needs git remote setup)
- [ ] Deploy backend to Railway
- [ ] Connect frontend to live backend API
- [ ] Deploy updated frontend to Vercel

## Day 2 — June 4, 2026

### Phase 3: New Dashboard Pages (Completed)
- ✅ **Historical Analytics** (`/analytics`)
  - Daily/Weekly toggle with trend charts
  - Visitor & Revenue composite chart (Recharts ComposedChart)
  - Conversion Rate trend line chart
  - Weekly Traffic Heatmap table (12 hours × 7 days)
  - Zone Popularity sparkline cards (5-week trends)
  - Queue Wait Time bar chart
  - Summary cards with WoW growth comparison
- ✅ **Live Store Monitor** (`/live`)
  - Simulated real-time event feed (2-5s interval)
  - Live stats bar (In-Store, In Queue, Entries, Exits, Purchases)
  - Event items with color-coded types and confidence scores
  - Zone Activity live progress bars
  - Camera Status panel (all 4 cameras)
  - Live Alerts section (queue building, high traffic)
  - Pause/Resume control
- ✅ **Dashboard Navigation** updated to 5 cards (added Analytics + Live)
- ✅ **Production build** verified — all 6 pages compile and prerender

### Architecture Decisions Made
- Simulated WebSocket for Live Monitor (easily swappable to real WS)
- Recharts ComposedChart for dual-axis visitor/revenue display
- Sparkline mini-charts for zone trend visualization

### Updated Page Count: 6
1. `/` — Executive Dashboard
2. `/heatmap` — Store Layout Heatmap
3. `/journeys` — Customer Journey Replay
4. `/insights` — Executive Insights + AI Findings
5. `/analytics` — Historical Analytics (Daily/Weekly)
6. `/live` — Live Store Monitor

### Next Steps
- [ ] Push to GitHub (needs git remote setup)
- [ ] Deploy updated frontend to Vercel
- [ ] Deploy backend to Railway
- [ ] Connect frontend to live backend API

