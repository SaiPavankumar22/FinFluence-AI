# Market Intelligence Influencer Analyzer

Monitors public financial influencers on Instagram, transcribes and translates their reels,
runs structured LLM analysis (stocks, IPOs, macro, sentiment, etc.), and displays everything in a clean Bootstrap dashboard with full edit/delete control over summaries.

## Features

- **Influencer monitoring** — Add any public Instagram account; the scheduler checks for new reels every N minutes and auto-processes them.
- **On-demand summarization** — Historical reels are not auto-processed; click **Summarize** on any reel to trigger the pipeline manually.
- **Full pipeline** — Download → audio extraction (ffmpeg) → speech-to-text (Sarvam) → translation → LLM structured analysis (Nebius).
- **Edit summaries** — Correct transcription errors: fix stock tickers, sentiment, sectors, risks, takeaways directly from the UI.
- **Delete summaries** — Remove a summary and re-run whenever you want a fresh take.
- **Analytics dashboard** — Charts for top stocks, IPOs, sectors, sentiment distribution, economic events, geopolitical events, and an influencer leaderboard.
- **Search** — Full-text search across all analyzed content by stock, topic, or influencer.

## Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI (async) + Motor (async MongoDB) + APScheduler |
| Frontend | HTML + Bootstrap 5.3 + Bootstrap Icons + vanilla JS (no framework build) |
| ASR | Sarvam (`saaras:v3`) |
| Translation | deep-translator (Google backend) |
| Analysis | Nebius API, `google/gemma-3-27b-it`, strict structured JSON output |
| Deploy | Frontend → Vercel · Backend → Render · DB → MongoDB Atlas |

## Project layout

```
backend/
  app/
    main.py                  FastAPI app, health, optional UI mount, CORS
    config.py                Env-driven settings (Pydantic)
    database.py              Motor + Atlas-friendly timeouts + indexes
    ...
frontend/
  *.html                     Static pages (Vercel)
  static/js/config.js        API_BASE (injected on Vercel build)
  vercel.json                Clean URL rewrites
Dockerfile                   Render image (Python + ffmpeg)
render.yaml                  Render service blueprint
```

## Local setup

### 1. Prerequisites

- Python 3.11+
- MongoDB Atlas (or local MongoDB)
- ffmpeg on PATH (`winget install ffmpeg` / `brew install ffmpeg` / `apt install ffmpeg`)

### 2. Install

```bash
cd backend
python -m venv venv

# Windows
.\venv\Scripts\activate

# macOS / Linux
source venv/bin/activate

pip install -r requirements.txt
```

### 3. Configure

```bash
cp .env.example .env
```

Minimum required in `.env`:

```env
MONGO_URI=mongodb+srv://USER:PASSWORD@CLUSTER.mongodb.net/?retryWrites=true&w=majority
MONGO_DB_NAME=market_intel
NEBIUS_API_KEY=your_nebius_key
SARVAM_API_SUBSCRIPTION_KEY=your_sarvam_key
SERVE_FRONTEND=true
CORS_ORIGINS=*
```

### 4. Run

```bash
# From the backend/ directory
uvicorn app.main:app --reload --port 8000
```

Open `http://localhost:8000`. Health check: `http://localhost:8000/health`.

---

## Production deploy (Atlas + Render + Vercel)

### A. MongoDB Atlas

1. Create a free/shared cluster.
2. **Database Access** → create a DB user.
3. **Network Access** → allow `0.0.0.0/0` (or lock to Render IPs if you prefer).
4. **Connect → Drivers** → copy the `mongodb+srv://...` URI into `MONGO_URI` (replace `<password>`).

### B. Backend on Render

1. Push this repo to GitHub.
2. In Render: **New → Blueprint** (uses `render.yaml`) or **Web Service** with **Docker**.
3. Set env vars (Dashboard → Environment):

| Key | Value |
|---|---|
| `MONGO_URI` | Atlas SRV URI |
| `MONGO_DB_NAME` | `market_intel` |
| `CORS_ORIGINS` | your Vercel URL, e.g. `https://your-app.vercel.app` |
| `SERVE_FRONTEND` | `false` |
| `APP_ENV` | `production` |
| `NEBIUS_API_KEY` | secret |
| `SARVAM_API_SUBSCRIPTION_KEY` | secret |
| `DOWNLOAD_DIR` | `/tmp/downloads` |

4. After deploy, note the API URL: `https://YOUR-SERVICE.onrender.com`  
   Confirm: `GET /health` returns `{"status":"ok",...}`.

**Notes**

- Use a **Starter+ / always-on** plan so the APScheduler keeps polling; free instances sleep and pause background jobs.
- Image includes **ffmpeg** (required for audio extraction).
- Temp media lives under `/tmp/downloads` and is cleaned after each reel.

### C. Frontend on Vercel

1. Import the same GitHub repo in Vercel.
2. Set **Root Directory** to `frontend`.
3. Framework: **Other**. Build command: `npm run build` (from `package.json`).
4. Add Environment Variable:

| Key | Value |
|---|---|
| `API_BASE` | `https://YOUR-SERVICE.onrender.com` (no trailing slash) |

5. Deploy. Open the Vercel URL — pages call the Render API via `API_BASE`.

After the Vercel URL is final, set Render `CORS_ORIGINS` to that exact origin (comma-separate if you have preview + production).

---

## API reference (key endpoints)

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Liveness / deploy health check |
| `GET` | `/api/dashboard/stats` | Summary stats for dashboard |
| `GET` | `/api/influencers` | List all monitored influencers |
| `POST` | `/api/influencers` | Add a new influencer |
| `GET` | `/api/influencers/{id}/reels` | Reels for one influencer |
| `GET` | `/api/reels/{id}` | Full reel detail (reel + transcript + analysis) |
| `POST` | `/api/reels/{id}/process` | Manually trigger pipeline |
| `POST` | `/api/reels/{id}/resummarize` | Re-run full pipeline (delete old + redo) |
| `PATCH` | `/api/reels/{id}/analysis` | Partially update analysis fields |
| `DELETE` | `/api/reels/{id}/analysis` | Delete transcript + analysis, reset to pending |
| `GET` | `/api/analytics/overview` | Aggregated charts data |
| `GET` | `/api/search?q=...` | Full-text search |

## MongoDB collections

| Collection | Key fields |
|---|---|
| `influencers` | `username`, `display_name`, `active`, `created_at` |
| `reels` | `reel_id`, `influencer_id`, `title`, `caption`, `thumbnail`, `reel_url`, `posted_at`, `processed`, `processing`, `processing_stage`, `processing_metrics`, `sentiment`, `process_error` |
| `transcripts` | `reel_id`, `language`, `original_text`, `english_translation` |
| `analyses` | `reel_id`, `headline`, `summary`, `sentiment`, `stocks`, `ipos`, `sectors`, `geopolitical_events`, `economic_events`, `risks`, `opportunities`, `takeaways` |

## Pipeline overview

```
Add Influencer
      │
      ▼
Fetch recent reels via Instagram mobile API
      │   (historical reels: processed=False, no auto-run)
      ▼
Scheduler polls every CHECK_INTERVAL_MINUTES
      │   new reel found → enqueue
      ▼
reel_processor.process_reel()
  1. Download video (direct URL or instaloader fallback)
  2. Extract audio (ffmpeg)
  3. Transcribe (Sarvam STT, chunked)
  4. Translate to English (deep-translator)
       └─ fallback: use Instagram caption if ASR is empty
  5. LLM analysis (Nebius / gemma-3-27b-it)
  6. Store transcript + analysis in MongoDB
```

## Important caveat: Instagram data access

There is no official public API for arbitrary reel scraping. `instagram_service.py` uses the
Instagram mobile API which is unofficial, subject to rate-limiting, and may break without notice.
Use it responsibly on public accounts only. You are responsible for complying with Instagram's Terms of Service.

## Production notes

- No authentication on the API or dashboard — add auth before exposing publicly.
- `reel_processor` runs inline in background tasks; for higher throughput, move to a task queue (Celery / RQ / arq).
- Keep a single Render instance so APScheduler does not duplicate work.
- `deep-translator`'s Google backend is best-effort; swap a paid translation API for reliability at scale.
- All data is stored indefinitely; add TTL indexes or an archival job for long-running deployments.
