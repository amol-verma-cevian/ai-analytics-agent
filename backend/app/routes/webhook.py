"""
Conversation event route — receives events from any source (chat UI, voice, API).

Flow: Client → POST /webhook → push to Redis queue → return 200 instantly
      ARQ worker picks up the job → processes through full pipeline
"""

import logging

from arq import create_pool
from arq.connections import RedisSettings
from fastapi import APIRouter

from app.config import settings
from app.models.schemas import WebhookPayload, WebhookResponse

logger = logging.getLogger(__name__)
router = APIRouter()

# Redis pool — initialized on first request
_redis_pool = None


async def get_redis_pool():
    """Lazy-initialize the Redis connection pool."""
    global _redis_pool
    if _redis_pool is None:
        _redis_pool = await create_pool(
            RedisSettings.from_dsn(settings.REDIS_URL)
        )
    return _redis_pool


@router.post("/", response_model=WebhookResponse)
async def handle_webhook(payload: WebhookPayload):
    """
    Receive conversation events from any client (dashboard chat, voice API, etc).

    Does NOT process the event — just pushes it to Redis queue
    and returns immediately. The ARQ worker handles processing.

    This keeps response time < 100ms regardless of pipeline complexity.
    """
    try:
        redis = await get_redis_pool()
        job = await redis.enqueue_job(
            "process_webhook",
            payload.dict(),
            _queue_name="voice_agent",
        )
        logger.info(f"[webhook] Enqueued job {job.job_id} for event '{payload.event}' call={payload.call_id}")

        return WebhookResponse(
            status="accepted",
            message=f"Job {job.job_id} enqueued for {payload.event}",
        )
    except Exception as e:
        logger.error(f"[webhook] Failed to enqueue: {e}")
        return WebhookResponse(
            status="accepted",
            message=f"Event received (queue unavailable, processing skipped)",
        )
