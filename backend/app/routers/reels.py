import logging
from typing import Any, Dict

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

from app.database import reels_col, transcripts_col, analyses_col
from app.services import reel_processor

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/reels", tags=["reels"])

ANALYSIS_KEYS = [
    "headline", "summary", "sentiment", "stocks", "ipos", "sectors",
    "geopolitical_events", "economic_events", "risks", "opportunities", "takeaways",
]


@router.get("")
async def list_reels(limit: int = 50, processed_only: bool = False):
    query = {"processed": True} if processed_only else {}
    out = []
    async for r in reels_col.find(query).sort("posted_at", -1).limit(limit):
        out.append({
            "id": str(r["_id"]),
            "reel_id": r["reel_id"],
            "influencer_id": r.get("influencer_id"),
            "title": r.get("title"),
            "thumbnail": r.get("thumbnail"),
            "posted_at": r.get("posted_at"),
            "processed": r.get("processed", False),
            "processing": r.get("processing", False),
            "sentiment": r.get("sentiment"),
            "process_error": r.get("process_error"),
        })
    return out


@router.get("/{reel_db_id}")
async def get_reel_detail(reel_db_id: str):
    try:
        oid = ObjectId(reel_db_id)
    except InvalidId:
        raise HTTPException(400, "Invalid id")

    reel = await reels_col.find_one({"_id": oid})
    if not reel:
        raise HTTPException(404, "Reel not found")

    transcript = await transcripts_col.find_one({"reel_id": reel["reel_id"]}) or {}
    analysis = await analyses_col.find_one({"reel_id": reel["reel_id"]}) or {}

    return {
        "reel": {
            "id": str(reel["_id"]),
            "reel_id": reel["reel_id"],
            "influencer_id": reel.get("influencer_id"),
            "title": reel.get("title"),
            "caption": reel.get("caption"),
            "thumbnail": reel.get("thumbnail"),
            "reel_url": reel.get("reel_url"),
            "posted_at": reel.get("posted_at"),
            "processed": reel.get("processed", False),
            "processing": reel.get("processing", False),
            "processing_stage": reel.get("processing_stage"),
            "processing_started_at": reel.get("processing_started_at"),
            "processing_metrics": reel.get("processing_metrics") or {},
            "transcript_language": reel.get("transcript_language"),
            "process_error": reel.get("process_error"),
        },
        "transcript": {
            "language": transcript.get("language"),
            "original_text": transcript.get("original_text"),
            "english_translation": transcript.get("english_translation"),
        },
        "analysis": {k: analysis.get(k) for k in ANALYSIS_KEYS},
    }


@router.post("/{reel_db_id}/process")
async def trigger_process(reel_db_id: str, background_tasks: BackgroundTasks):
    """Queue a reel for summarization. Returns immediately; processing runs in background."""
    try:
        oid = ObjectId(reel_db_id)
    except InvalidId:
        raise HTTPException(400, "Invalid id")

    reel = await reels_col.find_one({"_id": oid})
    if not reel:
        raise HTTPException(404, "Reel not found")

    if reel.get("processed"):
        logger.info("[reels] reel_id=%s already processed – skipping", reel["reel_id"])
        return {"status": "already_processed"}

    if reel.get("processing"):
        logger.info("[reels] reel_id=%s already processing – skipping", reel["reel_id"])
        return {"status": "already_processing"}

    logger.info("[reels] Queuing pipeline for reel_id=%s (manual trigger)", reel["reel_id"])
    await reels_col.update_one(
        {"_id": oid},
        {"$set": {
            "processing": True,
            "processed": False,
            "process_error": None,
            "processing_stage": "queued",
            "processing_started_at": None,
        }},
    )
    background_tasks.add_task(reel_processor.process_reel, reel)
    return {"status": "queued", "reel_id": reel["reel_id"]}


@router.delete("/{reel_db_id}/analysis")
async def delete_analysis(reel_db_id: str):
    """Delete the transcript and analysis for a reel, resetting it to unprocessed."""
    try:
        oid = ObjectId(reel_db_id)
    except InvalidId:
        raise HTTPException(400, "Invalid id")

    reel = await reels_col.find_one({"_id": oid})
    if not reel:
        raise HTTPException(404, "Reel not found")

    await transcripts_col.delete_many({"reel_id": reel["reel_id"]})
    await analyses_col.delete_many({"reel_id": reel["reel_id"]})

    await reels_col.update_one(
        {"_id": oid},
        {"$set": {
            "processed": False,
            "processing": False,
            "process_error": None,
            "sentiment": None,
            "topics": [],
        }},
    )
    logger.info("[reels] Deleted analysis for reel_id=%s", reel["reel_id"])
    return {"status": "deleted"}


class AnalysisPatch(BaseModel):
    summary: str | None = None
    headline: str | None = None
    sentiment: str | None = None
    stocks: list[str] | None = None
    ipos: list[str] | None = None
    sectors: list[str] | None = None
    risks: list[str] | None = None
    opportunities: list[str] | None = None
    takeaways: list[str] | None = None
    geopolitical_events: list[str] | None = None
    economic_events: list[str] | None = None


@router.patch("/{reel_db_id}/analysis")
async def patch_analysis(reel_db_id: str, payload: AnalysisPatch):
    """Partially update the stored analysis fields for a reel."""
    try:
        oid = ObjectId(reel_db_id)
    except InvalidId:
        raise HTTPException(400, "Invalid id")

    reel = await reels_col.find_one({"_id": oid})
    if not reel:
        raise HTTPException(404, "Reel not found")

    updates: Dict[str, Any] = {
        k: v for k, v in payload.model_dump().items() if v is not None
    }
    if not updates:
        raise HTTPException(422, "No fields provided to update")

    await analyses_col.update_one(
        {"reel_id": reel["reel_id"]},
        {"$set": updates},
        upsert=True,
    )

    if "sentiment" in updates:
        await reels_col.update_one({"_id": oid}, {"$set": {"sentiment": updates["sentiment"]}})

    logger.info("[reels] Patched analysis for reel_id=%s fields=%s", reel["reel_id"], list(updates))
    return {"status": "updated", "fields": list(updates)}


@router.post("/{reel_db_id}/resummarize")
async def resummarize_reel(reel_db_id: str, background_tasks: BackgroundTasks):
    try:
        oid = ObjectId(reel_db_id)
    except InvalidId:
        raise HTTPException(400, "Invalid id")

    reel = await reels_col.find_one({"_id": oid})
    if not reel:
        raise HTTPException(404, "Reel not found")

    if reel.get("processing"):
        logger.info("[reels] reel_id=%s already processing - resummarize skipped", reel["reel_id"])
        return {"status": "already_processing"}

    logger.info("[reels] Re-queuing pipeline for reel_id=%s (resummarize)", reel["reel_id"])
    await reels_col.update_one(
        {"_id": oid},
        {"$set": {
            "processing": True,
            "processed": False,
            "process_error": None,
            "processing_stage": "queued",
            "processing_started_at": None,
        }},
    )
    background_tasks.add_task(reel_processor.process_reel, reel)
    return {"status": "queued", "reel_id": reel["reel_id"]}
