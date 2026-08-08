import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.database import init_indexes
from app.services.scheduler import start_scheduler
from app.json_utils import MongoJSONResponse
from app.routers import influencers, reels, dashboard, analytics, search

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
# Keep terminal readable: hide library chatter, keep our pipeline/scheduler logs
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("apscheduler").setLevel(logging.WARNING)
logging.getLogger("faster_whisper").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("══════════════════════════════════════")
    logger.info(" Market Intelligence Analyzer starting")
    logger.info("══════════════════════════════════════")
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
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(influencers.router)
app.include_router(reels.router)
app.include_router(dashboard.router)
app.include_router(analytics.router)
app.include_router(search.router)

FRONTEND_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "frontend"))
app.mount("/static", StaticFiles(directory=os.path.join(FRONTEND_DIR, "static")), name="static")


def _page(name: str) -> FileResponse:
    return FileResponse(os.path.join(FRONTEND_DIR, name))


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
