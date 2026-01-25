"""APScheduler setup for background jobs."""

import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.jobs.reply_monitor import check_all_replies
from app.jobs.followup_sender import send_followups

logger = logging.getLogger(__name__)

# Global scheduler instance
scheduler: AsyncIOScheduler = None


def start_scheduler():
    """Start the background job scheduler."""
    global scheduler
    
    scheduler = AsyncIOScheduler()
    
    # Reply monitoring - every hour
    scheduler.add_job(
        check_all_replies,
        trigger=IntervalTrigger(hours=1),
        id="reply_monitor",
        name="Check for email replies",
        replace_existing=True,
    )
    
    # Follow-up sender - every 6 hours (checks for 14-day no-replies)
    scheduler.add_job(
        send_followups,
        trigger=IntervalTrigger(hours=6),
        id="followup_sender",
        name="Send follow-up emails",
        replace_existing=True,
    )
    
    scheduler.start()
    logger.info("Background scheduler started")


def shutdown_scheduler():
    """Shutdown the scheduler gracefully."""
    global scheduler
    
    if scheduler:
        scheduler.shutdown(wait=False)
        logger.info("Background scheduler shutdown")


def get_scheduler() -> AsyncIOScheduler:
    """Get the scheduler instance."""
    return scheduler


def run_job_now(job_id: str):
    """Manually trigger a job to run immediately."""
    if scheduler:
        job = scheduler.get_job(job_id)
        if job:
            job.modify(next_run_time=None)
            scheduler.add_job(
                job.func,
                id=f"{job_id}_manual",
                replace_existing=True,
            )
            logger.info(f"Manually triggered job: {job_id}")
