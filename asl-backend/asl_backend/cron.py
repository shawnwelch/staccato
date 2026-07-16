"""Render Cron entry point: re-scan every known channel on a schedule.

Usage: python -m asl_backend.cron
Enqueues one classify_channel job per channel on the batch queue and exits;
the worker does the heavy lifting.
"""

from __future__ import annotations

import asyncio
import logging

from sqlalchemy import select

from asl_backend.db import get_sessionmaker
from asl_backend.jobs import QUEUE_BATCH, app
from asl_backend.jobs.tasks import classify_channel
from asl_backend.models import Channel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main() -> None:
    async with app.open_async():
        sessionmaker = get_sessionmaker()
        async with sessionmaker() as session:
            channel_ids = (await session.scalars(select(Channel.id))).all()
        for channel_id in channel_ids:
            await classify_channel.configure(queue=QUEUE_BATCH).defer_async(channel_id=channel_id)
        logger.info("enqueued re-scans for %d channels", len(channel_ids))


if __name__ == "__main__":
    asyncio.run(main())
