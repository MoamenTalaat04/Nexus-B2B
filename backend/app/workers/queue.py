"""Enqueue helper (docs/CONTRACTS.md section 10). Business code enqueues jobs only through this."""

from typing import Any

from arq import ArqRedis, create_pool
from arq.connections import RedisSettings

from app.config import settings

_pool: ArqRedis | None = None


async def get_pool() -> ArqRedis:
    global _pool
    if _pool is None:
        _pool = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
    return _pool


async def enqueue(job_name: str, **kwargs: Any) -> str:
    """Enqueue `job_name` (e.g. "job_score_leads") with keyword args; returns the arq job id.

    Pass `_job_id="..."` to deduplicate, or `_defer_by=timedelta(...)` to delay (arq options).
    """
    pool = await get_pool()
    job = await pool.enqueue_job(job_name, **kwargs)
    if job is None:  # arq returns None when a job with the same _job_id already exists
        return str(kwargs.get("_job_id", ""))
    return job.job_id


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.aclose()
        _pool = None
