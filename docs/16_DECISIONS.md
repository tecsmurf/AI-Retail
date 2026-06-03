# Architecture Decision Records

## ADR-001: PostgreSQL over MongoDB

**Problem**: Choose a primary database for storing events, journeys, and analytics.

**Options Considered**:
1. MongoDB — Flexible schema, good for event storage
2. PostgreSQL — SQL analytics, relationships, mature ecosystem
3. ClickHouse — Columnar, optimized for analytics

**Decision**: PostgreSQL (via Neon serverless)

**Reasoning**:
- Analytics queries (GROUP BY, aggregates, joins) are naturally SQL
- Event relationships (journey → events) benefit from foreign keys
- Neon provides free serverless PostgreSQL
- SQLAlchemy 2.0 async support is excellent
- No need for ClickHouse-level scale at hackathon stage

**Tradeoffs**: Less flexible schema than MongoDB, but Pydantic handles input validation.

---

## ADR-002: YOLO11 over RT-DETR for Primary Detection

**Problem**: Choose the primary person detection model.

**Decision**: YOLO11n as primary, RT-DETR as optional enhancement.

**Reasoning**:
- YOLO11n offers best speed/accuracy tradeoff
- Well-documented, easy to deploy
- RT-DETR is slower but more accurate — available as upgrade path

---

## ADR-003: Event-Driven Architecture

**Problem**: How to store and process CV detections.

**Decision**: Convert all detections to business events immediately.

**Reasoning**:
- Business events are queryable and meaningful
- Events can be replayed for journey reconstruction
- Judges understand "ZONE_ENTER" better than raw bounding boxes
- Enables real-time alerting and analytics

---

## ADR-004: Demo Data Strategy

**Problem**: Dashboard needs data to look good even without live CV processing.

**Decision**: Generate realistic demo data in seed script.

**Reasoning**:
- 300 customer journeys with realistic zone patterns
- Allows immediate dashboard demonstration
- POS data from provided CSV
- Sample events from provided JSONL
- Seamless transition to real CV-generated events

---

## ADR-005: Next.js + Tailwind for Frontend

**Problem**: Choose frontend framework and styling approach.

**Decision**: Next.js 15 with Tailwind CSS v4.

**Reasoning**:
- SSR for SEO and performance
- App Router for modern patterns
- Tailwind for rapid premium UI development
- Easy Vercel deployment
- Recharts for data visualization
