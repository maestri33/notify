"""RQ queue setup — one queue per channel, shared Redis connection."""

from functools import cache

from redis import Redis
from rq import Queue, Retry

from app.config import settings
from app.models import Channel


@cache
def get_redis() -> Redis:
    return Redis.from_url(settings.redis_url)


@cache
def get_queue(channel: Channel) -> Queue:
    return Queue(channel.value, connection=get_redis())


# Retry policy: 3 attempts, exponential-ish backoff (60s, 300s, 900s)
DEFAULT_RETRY = Retry(max=3, interval=[60, 300, 900])
