"""High-level orchestrator that collects channel data and persists it to the DB."""

import asyncio
import logging
from typing import Any

from src.config import Config
from src.db.database import get_session
from src.db.repository import bulk_upsert_posts, upsert_channel
from src.parser.telegram_client import TelegramParser

logger = logging.getLogger(__name__)

_INTER_CHANNEL_DELAY: float = 0.5  # seconds between consecutive channel requests


class ChannelDataCollector:
    """Orchestrates parsing of a list of Telegram channels and persistence to PostgreSQL.

    Args:
        config: Application configuration instance.
    """

    def __init__(self, config: Config) -> None:
        self._config = config
        self._parser = TelegramParser(
            api_id=config.tg_api_id,
            api_hash=config.tg_api_hash,
            session_name=config.tg_session_name,
        )

    async def run(self, channels: list[str]) -> dict[str, Any]:
        """Parse all channels and save results to the database.

        Args:
            channels: List of Telegram channel usernames to process (without '@').

        Returns:
            Statistics dictionary with keys:
            - ``channels_processed``: number of successfully saved channels
            - ``posts_collected``: total number of posts upserted
            - ``channels_skipped``: number of channels that could not be fetched
            - ``errors``: number of unexpected errors
        """
        stats: dict[str, int] = {
            "channels_processed": 0,
            "posts_collected": 0,
            "channels_skipped": 0,
            "errors": 0,
        }

        limited_channels = channels[: self._config.channels_limit]
        total = len(limited_channels)

        logger.info("Starting parser for %d channels.", total)

        await self._parser.connect()
        try:
            for idx, username in enumerate(limited_channels, start=1):
                logger.info("[%d/%d] Processing channel: @%s", idx, total, username)
                try:
                    await self._process_channel(username, stats)
                except Exception as exc:
                    logger.error(
                        "Unexpected error processing @%s: %s", username, exc, exc_info=True
                    )
                    stats["errors"] += 1

                if idx < total:
                    await asyncio.sleep(_INTER_CHANNEL_DELAY)
        finally:
            await self._parser.disconnect()

        logger.info(
            "Parsing complete. Channels processed: %d, posts collected: %d, "
            "channels skipped: %d, errors: %d.",
            stats["channels_processed"],
            stats["posts_collected"],
            stats["channels_skipped"],
            stats["errors"],
        )
        return stats

    async def _process_channel(self, username: str, stats: dict[str, int]) -> None:
        """Fetch one channel's info and posts, then persist both to the database.

        Args:
            username: Channel username without '@'.
            stats: Mutable statistics dict that is updated in-place.
        """
        channel_info = await self._parser.get_channel_info(username)
        if channel_info is None:
            logger.info("Skipping @%s (could not retrieve info).", username)
            stats["channels_skipped"] += 1
            return

        async with get_session(self._config.db_url) as session:
            await upsert_channel(session, channel_info)

        logger.debug("Saved channel info for @%s (id=%d).", username, channel_info["channel_id"])

        posts = await self._parser.get_channel_posts(channel_info, self._config.posts_limit)
        post_count = len(posts)

        if posts:
            async with get_session(self._config.db_url) as session:
                saved = await bulk_upsert_posts(session, posts)
            logger.info(
                "Saved %d/%d posts for @%s.", saved, post_count, username
            )
            stats["posts_collected"] += saved
        else:
            logger.info("No posts retrieved for @%s.", username)

        stats["channels_processed"] += 1
