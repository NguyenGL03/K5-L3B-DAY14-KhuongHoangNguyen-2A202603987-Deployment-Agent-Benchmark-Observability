"""
Rate limiting (tiêu chí 7) — sliding window backed by Redis.
"""
import time
import uuid
from fastapi import HTTPException
import redis

from app.config import settings
from app.redis_client import r

WINDOW_SECONDS = 60


def check_rate_limit(key: str) -> None:
    """Enforce RATE_LIMIT_PER_MINUTE per API key using a Redis sorted-set sliding window."""
    if r is None:
        raise HTTPException(status_code=503, detail="Rate limiter unavailable (Redis not configured)")

    redis_key = f"ratelimit:{key}"
    now = time.time()
    window_start = now - WINDOW_SECONDS

    try:
        pipe = r.pipeline()
        pipe.zremrangebyscore(redis_key, 0, window_start)
        pipe.zcard(redis_key)
        _, current_count = pipe.execute()

        if current_count >= settings.rate_limit_per_minute:
            oldest = r.zrange(redis_key, 0, 0, withscores=True)
            retry_after = max(1, int((oldest[0][1] + WINDOW_SECONDS) - now) + 1) if oldest else WINDOW_SECONDS
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded",
                headers={"Retry-After": str(retry_after)},
            )

        member = f"{now}:{uuid.uuid4().hex}"
        pipe = r.pipeline()
        pipe.zadd(redis_key, {member: now})
        pipe.expire(redis_key, WINDOW_SECONDS)
        pipe.execute()
    except HTTPException:
        raise
    except redis.RedisError:
        raise HTTPException(status_code=503, detail="Rate limiter unavailable")
