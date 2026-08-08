# Market Intelligence Influencer Analyzer

Monitors public financial influencers on Instagram, transcribes and translates their reels,
runs structured LLM analysis (stocks, IPOs, macro, sentiment, etc.), and displays everything in a clean Bootstrap dashboard with full edit/delete control over summaries.

## Features

- **Influencer monitoring** — Add any public Instagram account; the scheduler checks for new reels every N minutes and auto-processes them.
- **On-demand summarization** — Historical reels are not auto-processed; click **Summarize** on any reel to trigger the pipeline manually.
- **Full pipeline** — Download → audio extraction (ffmpeg) → speech-to-text (faster-whisper) → translation → LLM structured analysis (Nebius).
- **Edit summaries** — Correct transcription errors: fix stock tickers, sentiment, sectors, risks, takeaways directly from the UI.
- **Delete summaries** — Remove a summary and re-run whenever you want a fresh take.
- **Analytics dashboard** — Charts for top stocks, IPOs, sectors, sentiment distribution, economic events, geopolitical events, and an influencer leaderboard.
- **Search** — Full-text search across all analyzed content by stock, topic, or influencer.

## Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI (async) + Motor (async MongoDB) + APScheduler |
| Frontend | HTML + Bootstrap 5.3 + Bootstrap Icons + vanilla JS (no build step) |
| ASR | faster-whisper (`medium` model, CPU) |
| Translation | deep-translator (Google backend) |
| Analysis | Nebius API, `google/gemma-3-27b-it`, strict structured JSON output |

## Project layout

```
backend/
  app/
    main.py                  FastAPI app, page routes, static file mount
    config.py                Env-driven settings (Pydantic)
    database.py              Motor collections + indexes
    schemas.py               Pydantic request models
    json_utils.py            ObjectId/datetime-safe JSON helpers
    routers/
      influencers.py         CRUD for influencer accounts
      reels.py               Reel detail, manual process trigger, edit & delete analysis
      dashboard.py           Dashboard stats API
      analytics.py           Aggregated charts: stocks, IPOs, sectors, sentiment, events
      search.py              Full-text search
    services/
      instagram_service.py   Reel discovery (Instagram mobile API) + video download
      media_utils.py         ffmpeg audio extraction
      asr_service.py         Whisper transcription with VAD retry logic
      translation_service.py English translation via deep-translator
      llm_service.py         Nebius LLM structured analysis
      reel_processor.py      Full pipeline orchestrator
      scheduler.py           APScheduler job — runs every CHECK_INTERVAL_MINUTES
frontend/
  index.html                 Dashboard (stats, pipeline status, latest reels)
  influencers.html           Influencer list + Add Influencer modal
  influencer_detail.html     Reel grid for one influencer (filter, summarize, polling)
  reel_analysis.html         Full analysis view with edit & delete controls
  analytics.html             Charts + influencer leaderboard
  search.html                Search by stock / IPO / topic / influencer
  static/{css,js}/
```

## Setup

### 1. Prerequisites

- Python 3.11+
- MongoDB (local or Atlas)
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

Edit `.env` — minimum required:

```env
MONGO_URI=mongodb://localhost:27017
NEBIUS_API_KEY=your_nebius_key_here

# Whisper — CPU-safe defaults (no CUDA required)
WHISPER_MODEL_SIZE=medium
WHISPER_DEVICE=cpu
WHISPER_COMPUTE_TYPE=int8
```

### 4. Run

```bash
# From the backend/ directory
.\venv\Scripts\uvicorn.exe app.main:app --reload --port 8000
```

Open `http://localhost:8000`.

## API reference (key endpoints)

| Method | Path | Description |
|---|---|---|
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
  3. Transcribe (faster-whisper medium, CPU)
       └─ VAD failure → retry without VAD → force lang=hi
  4. Translate to English (deep-translator)
       └─ fallback: use Instagram caption if ASR is empty
  5. LLM analysis (Nebius / gemma-3-27b-it)
       └─ returns JSON: headline, summary, sentiment, stocks,
          ipos, sectors, risks, opportunities, takeaways, events
  6. Store transcript + analysis in MongoDB
```

## Important caveat: Instagram data access

There is no official public API for arbitrary reel scraping. `instagram_service.py` uses the
Instagram mobile API (`api/v1/feed/user/{username}/username/`) which is unofficial, subject to
rate-limiting, and may break without notice. Use it responsibly:

- Only point it at public accounts.
- Do not use personal account credentials for automated scraping.
- You are responsible for complying with Instagram's Terms of Service.

The module exposes two functions (`get_profile_reels`, `download_reel_video`) so it can be
swapped for a licensed data provider, or extended to YouTube / Telegram / X, without touching
the rest of the app.

## Production notes

- No authentication on the API or dashboard — add auth (e.g. FastAPI OAuth2) before exposing publicly.
- `reel_processor` runs inline in background tasks; for higher throughput, move to a task queue (Celery / RQ / arq).
- The Whisper `medium` model uses ~1.5 GB RAM on CPU. Allow 2-4 min per reel on a typical laptop.
- `deep-translator`'s Google backend is best-effort; swap a paid translation API for reliability at scale.
- All data is stored indefinitely; add TTL indexes or an archival job for long-running deployments.
