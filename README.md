# PurpleSol — AI Retail Intelligence Platform

> **Google Analytics for Physical Retail Stores**

Transform CCTV footage into real-time retail analytics, customer journey intelligence, and conversion insights.

![Status](https://img.shields.io/badge/status-active-brightgreen)
![Python](https://img.shields.io/badge/python-3.11+-blue)
![Next.js](https://img.shields.io/badge/next.js-15-black)

---

## 🎯 What is PurpleSol?

Retailers know *what* customers buy, but have little visibility into *what happens before the purchase*.

PurpleSol bridges this gap by converting CCTV footage into actionable business intelligence:

- **Footfall Analytics** — Total visitors, peak hours, traffic patterns
- **Zone Intelligence** — Which shelves attract attention, dwell time analysis
- **Customer Journeys** — Path reconstruction from entry to exit
- **Conversion Tracking** — Visitor → Zone → Checkout → Purchase funnel
- **Queue Analytics** — Wait times, abandonment rates
- **Anomaly Detection** — Long queues, traffic drops, unusual patterns
- **POS Correlation** — Link in-store behavior to actual purchases

---

## 🏗️ Architecture

```
Video Streams / Uploads
        ↓
   FastAPI Backend  ←→  PostgreSQL (Neon)
        ↓                     ↑
   CV Processing          Redis (Upstash)
   (YOLO11 + ByteTrack)      ↑
        ↓                     |
   Event Engine  ──────→  WebSocket Layer
        ↓                     ↓
   Analytics Engine    Next.js Dashboard (Vercel)
```

---

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+
- PostgreSQL (or Docker)

### Backend

```bash
cd backend
python -m venv venv
.\venv\Scripts\activate      # Windows
pip install -r requirements.txt

# Set environment variables
cp ../.env.example .env

# Initialize database and seed demo data
python -m app.seed

# Start server
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Visit: `http://localhost:3000`

API Docs: `http://localhost:8000/docs`

---

## 📦 Tech Stack

| Layer | Technology |
|-------|-----------|
| CV Detection | YOLO11 |
| Tracking | ByteTrack |
| Backend | FastAPI + SQLAlchemy 2.0 |
| Database | PostgreSQL (Neon) |
| Cache | Redis (Upstash) |
| Frontend | Next.js 15 + Tailwind |
| Charts | Recharts |
| Deployment | Vercel + Railway + Docker |

---

## 📁 Project Structure

```
purple-sol/
├── backend/
│   ├── app/
│   │   ├── api/          # FastAPI routes
│   │   ├── cv/           # Computer vision pipeline
│   │   ├── models/       # SQLAlchemy models
│   │   ├── schemas/      # Pydantic schemas
│   │   ├── services/     # Business logic
│   │   ├── main.py       # App entry point
│   │   ├── config.py     # Settings
│   │   ├── database.py   # DB connection
│   │   └── seed.py       # Demo data
│   ├── venv/
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── app/          # Next.js pages
│   │   └── lib/          # API client, utils
│   └── package.json
├── docs/                 # Documentation
├── purple/               # Raw data assets
├── docker-compose.yml
└── .env.example
```

---

## 📊 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/stores` | List all stores |
| GET | `/api/stores/{id}` | Store overview with metrics |
| GET | `/api/analytics/{id}` | Full analytics |
| GET | `/api/analytics/{id}/footfall` | Footfall data |
| GET | `/api/analytics/{id}/zones` | Zone analytics |
| GET | `/api/analytics/{id}/conversion` | Conversion funnel |
| GET | `/api/analytics/{id}/journeys` | Customer journeys |
| GET | `/api/analytics/{id}/anomalies` | Detected anomalies |
| POST | `/api/events` | Ingest event |
| POST | `/api/events/batch` | Batch ingest |
| WS | `/ws/store/{id}` | Real-time updates |

---

## 🏬 Supported Stores

| Store | Cameras | Zones |
|-------|---------|-------|
| Store 1 (Mumbai) | 4 (2 zone, 1 entry, 1 billing) | 15 (Salm, TFS, Minimalist, Aqualogica, Foxtale, JC, Faces, Mars, Men's, L'Oreal, Beauty, Makeup, Fragrance, Billing, Entrance) |
| Store 2 (Mumbai) | 4 (2 entry, 1 billing, 1 zone) | 7 (Entrance, Left Wall, Right Wall, Center Display 1/2, Makeup Area, Billing) |

---

## 📄 License

Built for the Purplle Hackathon 2026.
