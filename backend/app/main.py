import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import init_indexes, ping_database
from app.json_utils import MongoJSONResponse
from app.routers import analytics, dashboard, influencers, reels, search
from app.services.scheduler import start_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("apscheduler").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("══════════════════════════════════════")
    logger.info(" Market Intelligence Analyzer starting")
    logger.info(" env=%s  serve_frontend=%s", settings.app_env, settings.serve_frontend)
    logger.info("══════════════════════════════════════")
    Path(settings.download_dir).mkdir(parents=True, exist_ok=True)
    await ping_database()
    await init_indexes()
    logger.info("Database indexes initialized")
    start_scheduler()
    yield
    logger.info("Shutting down…")


app = FastAPI(
    title="Market Intelligence Influencer Analyzer",
    lifespan=lifespan,
    default_response_class=MongoJSONResponse,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(influencers.router)
app.include_router(reels.router)
app.include_router(dashboard.router)
app.include_router(analytics.router)
app.include_router(search.router)


@app.get("/health")
@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "env": settings.app_env,
        "db": settings.mongo_db_name,
    }


def _mount_frontend() -> None:
    static_dir = FRONTEND_DIR / "static"
    if not static_dir.is_dir():
        logger.warning("Frontend static dir missing at %s — skipping UI mount", static_dir)
        return

    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    def _page(name: str) -> FileResponse:
        return FileResponse(FRONTEND_DIR / name)

    @app.get("/")
    async def dashboard_page():
        return _page("index.html")

    @app.get("/influencers")
    async def influencers_page():
        return _page("influencers.html")

    @app.get("/influencer/{influencer_id}")
    async def influencer_detail_page(influencer_id: str):
        return _page("influencer_detail.html")

    @app.get("/reel/{reel_db_id}")
    async def reel_page(reel_db_id: str):
        return _page("reel_analysis.html")

    @app.get("/analytics")
    async def analytics_page():
        return _page("analytics.html")

    @app.get("/search")
    async def search_page():
        return _page("search.html")


if settings.serve_frontend:
    _mount_frontend()
