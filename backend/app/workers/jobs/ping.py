"""Demo job proving the worker and auto-discovery work. Safe to keep."""

import logging
from typing import Any

logger = logging.getLogger("app.worker")


async def job_ping(ctx: dict[str, Any], message: str = "pong") -> str:
    logger.info("job_ping: %s", message)
    return message
