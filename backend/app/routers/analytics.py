from fastapi import APIRouter

from app.database import analyses_col, reels_col, influencers_col

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


async def _top_field(field: str, limit: int = 15):
    pipeline = [
        {"$unwind": f"${field}"},
        {"$match": {field: {"$ne": None, "$ne": ""}}},
        {"$group": {"_id": f"${field}", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": limit},
    ]
    return [doc async for doc in analyses_col.aggregate(pipeline)]


@router.get("/overview")
async def analytics_overview():
    top_stocks = await _top_field("stocks")
    top_ipos = await _top_field("ipos")
    top_sectors = await _top_field("sectors")
    top_risks = await _top_field("risks", limit=10)
    top_economic_events = await _top_field("economic_events", limit=10)
    top_geopolitical_events = await _top_field("geopolitical_events", limit=10)

    sentiment_pipeline = [
        {"$group": {"_id": "$sentiment", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
    ]
    sentiment_distribution = [doc async for doc in analyses_col.aggregate(sentiment_pipeline)]

    total_analyzed = await reels_col.count_documents({"processed": True})
    total_reels = await reels_col.count_documents({})
    total_influencers = await influencers_col.count_documents({})
    processing_now = await reels_col.count_documents({"processing": True})

    influencer_pipeline = [
        {"$match": {"processed": True}},
        {"$group": {"_id": "$influencer_id", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 10},
    ]
    raw_by_influencer = [doc async for doc in reels_col.aggregate(influencer_pipeline)]

    by_influencer = []
    for row in raw_by_influencer:
        inf_id = row["_id"]
        try:
            from bson import ObjectId
            inf = await influencers_col.find_one({"_id": ObjectId(inf_id)}) if inf_id else None
        except Exception:
            inf = None
        by_influencer.append({
            "id": str(inf_id) if inf_id else None,
            "username": inf["username"] if inf else str(inf_id),
            "display_name": inf.get("display_name", "") if inf else "",
            "count": row["count"],
        })

    return {
        "top_stocks": top_stocks,
        "top_ipos": top_ipos,
        "top_sectors": top_sectors,
        "top_risks": top_risks,
        "top_economic_events": top_economic_events,
        "top_geopolitical_events": top_geopolitical_events,
        "sentiment_distribution": sentiment_distribution,
        "totals": {
            "total_analyzed": total_analyzed,
            "total_reels": total_reels,
            "total_influencers": total_influencers,
            "processing_now": processing_now,
        },
        "by_influencer": by_influencer,
    }
