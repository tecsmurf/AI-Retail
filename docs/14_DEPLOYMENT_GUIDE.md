# Deployment Guide — Step by Step

## Quick Deploy Checklist

### Step 1: Initialize Git Repository
```bash
cd "c:\Users\adity\OneDrive\Desktop\purple sol"
git init
git add .
git commit -m "PurpleSol v1.0 - AI Retail Intelligence Platform"
```

### Step 2: Create GitHub Repository
1. Go to https://github.com/new
2. Name: `purplesol` or `retail-intelligence`
3. Private repo
4. **Don't** add README (we have one)
5. Push:
```bash
git remote add origin https://github.com/YOUR_USERNAME/purplesol.git
git branch -M main
git push -u origin main
```

---

## Frontend → Vercel (5 minutes)

1. Go to https://vercel.com/new
2. Click "Import Git Repository"
3. Select your `purplesol` repo
4. Configure:
   - **Framework Preset**: Next.js
   - **Root Directory**: `frontend`
   - **Build Command**: `npm run build`
   - **Output Directory**: `.next`
5. Environment Variables (optional for now):
   - `NEXT_PUBLIC_API_URL` = `https://purplesol-api.up.railway.app` (add after Railway deploy)
6. Click **Deploy**

**Custom domain**: After deploy, go to Settings → Domains → add `retail-intelligence.vercel.app` or your custom domain.

The dashboard works standalone with demo data — no backend needed for the demo!

---

## Backend → Railway (10 minutes)

1. Go to https://railway.com/new
2. Click "Deploy from GitHub"
3. Select your repo
4. Set **Root Directory**: `backend`
5. Environment Variables:
```env
DATABASE_URL=postgresql+asyncpg://YOUR_NEON_URL
REDIS_URL=redis://localhost:6379/0
API_CORS_ORIGINS=https://your-app.vercel.app,http://localhost:3000
APP_ENV=production
LOG_LEVEL=INFO
SECRET_KEY=your-production-secret-key-here
```
6. Railway auto-detects the `Dockerfile`
7. Click **Deploy**

The API will be at: `https://purplesol-api.up.railway.app`

---

## Database → Neon PostgreSQL (3 minutes)

1. Go to https://neon.tech
2. Sign up (free tier: 512MB storage, 1 project)
3. Create project: `purplesol`
4. Create database: `purplesol`
5. Copy the connection string
6. Format for asyncpg:
```
postgresql+asyncpg://USER:PASSWORD@EP.us-east-2.aws.neon.tech/purplesol?sslmode=require
```
7. Set this as `DATABASE_URL` in Railway

### Seed the database
After Railway is running:
```bash
# In Railway console or local with DATABASE_URL set:
python -m app.seed
python -m app.cv.ingest_events
```

---

## Redis → Upstash (2 minutes)

1. Go to https://upstash.com
2. Create Redis database (free tier: 10K commands/day)
3. Copy the connection URL
4. Set as `REDIS_URL` in Railway

**Note**: Redis is optional for MVP. The API works without it (caching disabled).

---

## Verify Deployment

1. Frontend: Visit your Vercel URL
   - ✅ Dashboard loads with all 4 pages
   - ✅ Heatmap, Journey Replay, Executive Insights
2. Backend: Visit `https://your-railway-url/docs`
   - ✅ Swagger UI loads
   - ✅ `/` returns healthy status
3. Database: Check Railway logs
   - ✅ "Database initialized" message
4. API test:
   - `GET /api/video/events/summary` returns event counts

---

## Alternative: Static Frontend Only (Fastest)

Since the dashboard uses demo data, you can deploy JUST the frontend:

```bash
cd frontend
npx vercel --prod
```

This gives you a working URL in under 2 minutes. No backend needed.

---

## Cost Summary

| Service | Free Tier | Limits |
|---------|-----------|--------|
| Vercel | Yes | 100GB bandwidth/month |
| Railway | $5 credit | 500 hours/month |
| Neon | Yes | 512MB storage |
| Upstash | Yes | 10K commands/day |

**Total: $0/month for hackathon demo**
