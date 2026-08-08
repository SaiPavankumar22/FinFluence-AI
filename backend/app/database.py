from motor.motor_asyncio import AsyncIOMotorClient
from app.config import settings

client = AsyncIOMotorClient(settings.mongo_uri)
db = client[settings.mongo_db_name]

influencers_col = db["influencers"]
reels_col = db["reels"]
transcripts_col = db["transcripts"]
analyses_col = db["analyses"]


async def init_indexes():
    await influencers_col.create_index("username", unique=True)
    await reels_col.create_index("reel_id", unique=True)
    await reels_col.create_index("influencer_id")
    await reels_col.create_index("posted_at")
    await transcripts_col.create_index("reel_id", unique=True)
    await analyses_col.create_index("reel_id", unique=True)
    await analyses_col.create_index("stocks")
    await analyses_col.create_index("sectors")
    await analyses_col.create_index("ipos")
