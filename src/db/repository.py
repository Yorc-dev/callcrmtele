"""Repository helpers for upsert operations on channels and posts."""

import logging
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def upsert_channel(session: AsyncSession, channel_data: dict[str, Any]) -> None:
    """Insert or update a channel record.

    On conflict (channel_id already exists) all mutable fields are updated.

    Args:
        session: Open async SQLAlchemy session.
        channel_data: Dictionary with channel fields matching the ``channels`` table.
    """
    stmt = text(
        """
        INSERT INTO channels
            (channel_id, username, title, description, subscribers_count,
             avatar_url, is_verified, is_scam, updated_at)
        VALUES
            (:channel_id, :username, :title, :description, :subscribers_count,
             :avatar_url, :is_verified, :is_scam, NOW())
        ON CONFLICT (channel_id) DO UPDATE SET
            username          = EXCLUDED.username,
            title             = EXCLUDED.title,
            description       = EXCLUDED.description,
            subscribers_count = EXCLUDED.subscribers_count,
            avatar_url        = EXCLUDED.avatar_url,
            is_verified       = EXCLUDED.is_verified,
            is_scam           = EXCLUDED.is_scam,
            updated_at        = NOW()
        """
    )
    await session.execute(
        stmt,
        {
            "channel_id": channel_data.get("channel_id"),
            "username": channel_data.get("username"),
            "title": channel_data.get("title"),
            "description": channel_data.get("description"),
            "subscribers_count": channel_data.get("subscribers_count"),
            "avatar_url": channel_data.get("avatar_url"),
            "is_verified": channel_data.get("is_verified", False),
            "is_scam": channel_data.get("is_scam", False),
        },
    )


async def upsert_post(session: AsyncSession, post_data: dict[str, Any]) -> None:
    """Insert or update a single post record.

    On conflict (channel_id, message_id already exists) the counters that can
    change over time are refreshed.

    Args:
        session: Open async SQLAlchemy session.
        post_data: Dictionary with post fields matching the ``posts`` table.
    """
    stmt = text(
        """
        INSERT INTO posts
            (message_id, channel_id, text, published_at, views, forwards,
             replies_count, reactions_count, has_media, media_type, updated_at)
        VALUES
            (:message_id, :channel_id, :text, :published_at, :views, :forwards,
             :replies_count, :reactions_count, :has_media, :media_type, NOW())
        ON CONFLICT (channel_id, message_id) DO UPDATE SET
            text            = EXCLUDED.text,
            views           = EXCLUDED.views,
            forwards        = EXCLUDED.forwards,
            replies_count   = EXCLUDED.replies_count,
            reactions_count = EXCLUDED.reactions_count,
            has_media       = EXCLUDED.has_media,
            media_type      = EXCLUDED.media_type,
            updated_at      = NOW()
        """
    )
    await session.execute(
        stmt,
        {
            "message_id": post_data.get("message_id"),
            "channel_id": post_data.get("channel_id"),
            "text": post_data.get("text"),
            "published_at": post_data.get("published_at"),
            "views": post_data.get("views", 0),
            "forwards": post_data.get("forwards", 0),
            "replies_count": post_data.get("replies_count", 0),
            "reactions_count": post_data.get("reactions_count", 0),
            "has_media": post_data.get("has_media", False),
            "media_type": post_data.get("media_type"),
        },
    )


async def bulk_upsert_posts(session: AsyncSession, posts: list[dict[str, Any]]) -> int:
    """Perform a bulk upsert of posts records.

    Args:
        session: Open async SQLAlchemy session.
        posts: List of post data dictionaries.

    Returns:
        Number of records that were inserted or updated.
    """
    if not posts:
        return 0

    count = 0
    for post_data in posts:
        await upsert_post(session, post_data)
        count += 1

    logger.debug("bulk_upsert_posts: processed %d records", count)
    return count
