"""
APScheduler — Scheduled Analytics Tasks.

Runs periodic analytics jobs:
- Anomaly scan every 15 minutes
- Daily summary generation at 9am

Why scheduled analytics?
- "Push" AI > "Pull" AI — proactively detect issues
- Users shouldn't have to ask for alerts — the system finds them
"""

import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.services.anomaly_service import scan_all_anomalies
from app.services.ws_manager import manager

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


def setup_scheduler():
    """Configure and start the analytics scheduler."""
    # Anomaly scan every 15 minutes
    scheduler.add_job(
        _run_anomaly_scan,
        "interval",
        minutes=15,
        id="anomaly_scan",
        replace_existing=True,
    )

    scheduler.start()
    logger.info("[scheduler] Analytics scheduler started")


async def _run_anomaly_scan():
    """Periodic anomaly scan — pushes alerts to dashboard."""
    logger.info("[scheduler] Running periodic anomaly scan...")
    try:
        anomalies = scan_all_anomalies()
        if anomalies:
            for a in anomalies:
                await manager.broadcast("anomaly_detected", a)
            logger.info(f"[scheduler] Found {len(anomalies)} anomalies")
        else:
            logger.info("[scheduler] No anomalies detected")
    except Exception as e:
        logger.error(f"[scheduler] Anomaly scan failed: {e}")


def shutdown_scheduler():
    """Stop the scheduler gracefully."""
    if scheduler.running:
        scheduler.shutdown()
        logger.info("[scheduler] Scheduler stopped")
