"""
Cost guard (tiêu chí 8) — track daily LLM spend in Redis.
"""
from datetime import datetime, timezone
from fastapi import HTTPException
import redis

from app.config import settings
from app.redis_client import r

PRICE_INPUT_PER_1K = 0.00015
PRICE_OUTPUT_PER_1K = 0.0006
BUDGET_TTL_SECONDS = 2 * 24 * 3600


def _budget_key(key: str = "default") -> str:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return f"cost:{today}:{key}"


def check_budget(key: str = "default") -> None:
    """Check whether remaining daily budget allows a request; raise 402 if exhausted."""
    if r is None:
        return
    try:
        spent = float(r.get(_budget_key(key)) or 0.0)
    except redis.RedisError:
        raise HTTPException(status_code=503, detail="Cost guard unavailable")

    if spent >= settings.daily_budget_usd:
        raise HTTPException(
            status_code=402,
            detail="Budget exceeded",
        )


def record_cost(input_tokens: int, output_tokens: int, key: str = "default") -> float:
    """Accumulate request cost in Redis and return the request cost in USD."""
    cost = (input_tokens / 1000.0) * PRICE_INPUT_PER_1K + (
        output_tokens / 1000.0
    ) * PRICE_OUTPUT_PER_1K
    if r is not None:
        try:
            bkey = _budget_key(key)
            pipe = r.pipeline()
            pipe.incrbyfloat(bkey, cost)
            pipe.expire(bkey, BUDGET_TTL_SECONDS)
            pipe.execute()
        except redis.RedisError:
            pass
    return round(cost, 8)
