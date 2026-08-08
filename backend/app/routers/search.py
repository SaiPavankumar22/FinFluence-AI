from bson import ObjectId
from fastapi import APIRouter, Query

from app.database import analyses_col, reels_col, influencers_col

router = APIRouter(prefix="/api/search", tags=["search"])


@router.get("")
async def search(q: str = Query(..., min_length=1)):
    regex = {"$regex": q, "$options": "i"}

    analysis_query = {
        "$or": [
            {"stocks": regex},
            {"ipos": regex},
            {"sectors": regex},
            {"geopolitical_events": regex},
            {"economic_events": regex},
            {"summary": regex},
            {"takeaways": regex},
        ]
    }

    reel_results = []
    async for analysis in analyses_col.find(analysis_query).limit(50):
        reel = await reels_col.find_one({"reel_id": analysis["reel_id"]})
        if not reel:
            continue
        influencer = None
        if reel.get("influencer_id"):
            influencer = await influencers_col.find_one({"_id": ObjectId(reel["influencer_id"])})
        reel_results.append({
            "reel_db_id": str(reel["_id"]),
            "title": reel.get("title"),
            "thumbnail": reel.get("thumbnail"),
            "sentiment": analysis.get("sentiment"),
            "summary": analysis.get("summary"),
            "influencer_username": influencer.get("username") if influencer else None,
        })

    influencer_results = []
    async for inf in influencers_col.find({"username": regex}):
        influencer_results.append({"id": str(inf["_id"]), "username": inf["username"]})

    return {"reels": reel_results, "influencers": influencer_results}
