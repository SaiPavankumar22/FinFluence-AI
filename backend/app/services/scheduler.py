"""APScheduler job: periodically checks active influencers for new reels and processes them."""
import asyncio
import logging
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.database import influencers_col, reels_col
from app.services import instagram_service, reel_processor
from app.config import settings

logger = logging.getLogger(__name__)
scheduler = AsyncIOScheduler()

# Quiet the noisy APScheduler internals
logging.getLogger("apscheduler").setLevel(logging.WARNING)


async def check_influencers() -> None:
    influencer_count = 0
    new_reel_count = 0
    processing_tasks = []

    async for influencer in influencers_col.find({"active": True}):
        username = influencer["username"]
        influencer_count += 1

        try:
            reels, _ = instagram_service.get_profile_reels(username, limit=10)
        except Exception as e:
            logger.error("[scheduler] @%s fetch failed: %s", username, e)
            continue

        for r in reels:
            existing = await reels_col.find_one({"reel_id": r["reel_id"]})
            if existing:
                continue

            logger.info(
                "[scheduler] NEW reel @%s  reel_id=%s  → auto-processing",
                username, r["reel_id"],
            )
            doc = {
                "reel_id": r["reel_id"],
                "influencer_id": str(influencer["_id"]),
                "title": r["title"],
                "caption": r["caption"],
                "thumbnail": r["thumbnail"],
                "reel_url": r["reel_url"],
                "posted_at": r["posted_at"],
                "video_url": r.get("video_url"),
                "media_pk": r.get("media_pk"),
                "processed": False,
                "processing": False,
                "discovered_at": datetime.now(timezone.utc),
            }
            await reels_col.insert_one(doc)
            new_reel_count += 1
            processing_tasks.append(asyncio.create_task(reel_processor.process_reel(doc)))

    if processing_tasks:
        await asyncio.gather(*processing_tasks, return_exceptions=True)

    if new_reel_count:
        logger.info(
            "[scheduler] Done – %d influencer(s), %d NEW reel(s) processed",
            influencer_count, new_reel_count,
        )
    else:
        logger.info(
            "[scheduler] Done – %d influencer(s), no new reels",
            influencer_count,
        )


def start_scheduler() -> None:
    scheduler.add_job(
        check_influencers,
        "interval",
        minutes=settings.check_interval_minutes,
        id="check_influencers",
        replace_existing=True,
        next_run_time=datetime.now(timezone.utc),
    )
    scheduler.start()
    logger.info("[scheduler] Started (every %d min)", settings.check_interval_minutes)
