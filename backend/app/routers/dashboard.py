import logging
from datetime import datetime, timezone

from fastapi import APIRouter

from app.database import influencers_col, reels_col, analyses_col

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/stats")
async def get_stats():
    total_influencers = await influencers_col.count_documents({})
    total_reels = await reels_col.count_documents({})
    processed_reels = await reels_col.count_documents({"processed": True})
    pending_reels = await reels_col.count_documents({"processed": False, "processing": {"$ne": True}})
    processing_now = await reels_col.count_documents({"processing": True})
    failed_reels = await reels_col.count_documents({"processed": False, "process_error": {"$ne": None}})

    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    new_reels_today = await reels_col.count_documents({"posted_at": {"$gte": today_start}})

    trending_pipeline = [
        {"$project": {"topics": {"$concatArrays": [
            {"$ifNull": ["$sectors", []]},
            {"$ifNull": ["$stocks", []]}
        ]}}},
        {"$unwind": "$topics"},
        {"$match": {"topics": {"$exists": True, "$ne": None, "$ne": ""}}},
        {"$group": {"_id": "$topics", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 10},
    ]
    trending = [doc async for doc in analyses_col.aggregate(trending_pipeline)]

    latest = []
    async for reel in reels_col.find({"processed": True}).sort("processed_at", -1).limit(6):
        analysis = await analyses_col.find_one({"reel_id": reel["reel_id"]}) or {}
        latest.append({
            "reel_db_id": str(reel["_id"]),
            "title": reel.get("title"),
            "thumbnail": reel.get("thumbnail"),
            "sentiment": analysis.get("sentiment"),
            "summary": analysis.get("summary"),
            "stocks": analysis.get("stocks", [])[:4],
            "sectors": analysis.get("sectors", [])[:3],
            "posted_at": reel.get("posted_at"),
            "processed_at": reel.get("processed_at"),
        })

    logger.debug(
        "[dashboard] stats: influencers=%d reels=%d processed=%d pending=%d",
        total_influencers, total_reels, processed_reels, pending_reels,
    )

    return {
        "total_influencers": total_influencers,
        "total_reels": total_reels,
        "processed_reels": processed_reels,
        "pending_reels": pending_reels,
        "processing_now": processing_now,
        "failed_reels": failed_reels,
        "new_reels_today": new_reels_today,
        "trending_topics": trending,
        "latest_analyses": latest,
    }
