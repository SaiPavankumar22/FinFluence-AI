import logging
from datetime import datetime, timezone

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, HTTPException

from app.database import influencers_col, reels_col
from app.schemas import InfluencerCreate
from app.services import instagram_service
from app.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/influencers", tags=["influencers"])


def _oid(id_str: str) -> ObjectId:
    try:
        return ObjectId(id_str)
    except InvalidId:
        raise HTTPException(400, "Invalid id")


def serialize_influencer(doc: dict, reel_count: int = 0, processed_count: int = 0) -> dict:
    return {
        "id": str(doc["_id"]),
        "username": doc["username"],
        "display_name": doc.get("display_name"),
        "active": doc.get("active", True),
        "created_at": doc.get("created_at"),
        "reel_count": reel_count,
        "processed_count": processed_count,
    }


@router.get("")
async def list_influencers():
    out = []
    async for doc in influencers_col.find().sort("created_at", -1):
        inf_id = str(doc["_id"])
        count = await reels_col.count_documents({"influencer_id": inf_id})
        processed = await reels_col.count_documents({"influencer_id": inf_id, "processed": True})
        out.append(serialize_influencer(doc, count, processed))
    return out


@router.post("")
async def add_influencer(payload: InfluencerCreate):
    username = payload.username.strip().lstrip("@").lower()
    logger.info("[influencers] Adding new influencer @%s", username)

    existing = await influencers_col.find_one({"username": username})
    if existing:
        raise HTTPException(400, "Influencer already exists")

    try:
        logger.info("[influencers] Fetching profile reels for @%s (limit=%d)…", username, settings.historical_reels_limit)
        reels, full_name = instagram_service.get_profile_reels(
            username, limit=settings.historical_reels_limit
        )
        logger.info("[influencers] @%s: fetched %d reels, display_name=%r", username, len(reels), full_name)
    except Exception as e:
        logger.error("[influencers] Failed to fetch @%s: %s", username, e)
        raise HTTPException(400, f"Could not fetch profile '{username}': {e}")

    doc = {
        "username": username,
        "display_name": payload.display_name or full_name,
        "active": True,
        "created_at": datetime.now(timezone.utc),
    }
    result = await influencers_col.insert_one(doc)
    influencer_id = str(result.inserted_id)
    logger.info("[influencers] Created influencer db_id=%s for @%s", influencer_id, username)

    inserted = 0
    for r in reels:
        existing_reel = await reels_col.find_one({"reel_id": r["reel_id"]})
        if existing_reel:
            continue
        await reels_col.insert_one({
            "reel_id": r["reel_id"],
            "influencer_id": influencer_id,
            "title": r["title"],
            "caption": r["caption"],
            "thumbnail": r["thumbnail"],
            "reel_url": r["reel_url"],
            "posted_at": r["posted_at"],
            "video_url": r.get("video_url"),
            "media_pk": r.get("media_pk"),
            "processed": False,
            "processing": False,
            # Historical reels are stored but NOT auto-processed.
            # Use the "Summarize" button on the influencer page to process manually.
        })
        inserted += 1

    logger.info("[influencers] Stored %d new reels for @%s (not auto-processed – use Summarize button)", inserted, username)
    doc["_id"] = result.inserted_id
    return serialize_influencer(doc, inserted, 0)


@router.get("/{influencer_id}")
async def get_influencer(influencer_id: str):
    doc = await influencers_col.find_one({"_id": _oid(influencer_id)})
    if not doc:
        raise HTTPException(404, "Influencer not found")

    reels = []
    async for r in reels_col.find({"influencer_id": influencer_id}).sort("posted_at", -1):
        reels.append({
            "id": str(r["_id"]),
            "reel_id": r["reel_id"],
            "title": r.get("title"),
            "caption": r.get("caption"),
            "thumbnail": r.get("thumbnail"),
            "reel_url": r.get("reel_url"),
            "posted_at": r.get("posted_at"),
            "processed": r.get("processed", False),
            "processing": r.get("processing", False),
            "process_error": r.get("process_error"),
            "sentiment": r.get("sentiment"),
            "topics": r.get("topics", []),
        })

    processed_count = sum(1 for r in reels if r["processed"])
    return {
        "influencer": serialize_influencer(doc, len(reels), processed_count),
        "reels": reels,
    }


@router.post("/{influencer_id}/toggle")
async def toggle_influencer(influencer_id: str):
    doc = await influencers_col.find_one({"_id": _oid(influencer_id)})
    if not doc:
        raise HTTPException(404, "Influencer not found")
    new_state = not doc.get("active", True)
    await influencers_col.update_one({"_id": doc["_id"]}, {"$set": {"active": new_state}})
    logger.info("[influencers] @%s toggled active=%s", doc["username"], new_state)
    return {"active": new_state}


@router.post("/{influencer_id}/reels/{reel_db_id}/reprocess")
async def reprocess_reel(influencer_id: str, reel_db_id: str):
    from fastapi import BackgroundTasks
    from app.services import reel_processor
    reel = await reels_col.find_one({"_id": _oid(reel_db_id)})
    if not reel:
        raise HTTPException(404, "Reel not found")
    await reels_col.update_one(
        {"_id": reel["_id"]},
        {"$set": {
            "processing": True,
            "processed": False,
            "process_error": None,
            "processing_stage": "queued",
            "processing_started_at": None,
        }},
    )
    import asyncio
    asyncio.create_task(reel_processor.process_reel(reel))
    return {"status": "queued"}
