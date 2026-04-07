"""
Gateway Rate Limiter
Redis-based sliding window rate limiting.
"""
import redis.asyncio as redis
from fastapi import HTTPException

from app.Config import config

redis_client: redis.Redis = None


async def init_redis():
    global redis_client
    redis_client = redis.from_url(config.REDIS_URL, decode_responses=True)


async def close_redis():
    global redis_client
    if redis_client:
        await redis_client.close()


async def check_rate_limit(
    user_id: int,
    endpoint: str = "default",
    max_requests: int = None,
    window_seconds: int = None,
):
    """Check if user has exceeded rate limit. Raises 429 if exceeded."""
    if not redis_client:
        return  # Redis not connected, skip rate limiting

    max_req = max_requests or config.RATE_LIMIT_REQUESTS
    window = window_seconds or config.RATE_LIMIT_WINDOW_SECONDS

    key = f"rate:{user_id}:{endpoint}"

    current = await redis_client.get(key)
    if current and int(current) >= max_req:
        ttl = await redis_client.ttl(key)
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded. Try again in {ttl} seconds.",
            headers={"Retry-After": str(ttl)},
        )

    pipe = redis_client.pipeline()
    pipe.incr(key)
    pipe.expire(key, window)
    await pipe.execute()


async def check_upload_rate(user_id: int):
    """Specific rate limit for uploads (stricter)."""
    await check_rate_limit(
        user_id,
        endpoint="upload",
        max_requests=config.UPLOAD_RATE_LIMIT,
        window_seconds=config.UPLOAD_RATE_WINDOW,
    )