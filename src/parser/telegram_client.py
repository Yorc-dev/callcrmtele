"""Telethon-based Telegram client with error handling and retry logic."""

import asyncio
import logging
from typing import Any

from telethon import TelegramClient
from telethon.errors import (
    ChannelPrivateError,
    FloodWaitError,
    UsernameNotOccupiedError,
)
from telethon.tl.functions.channels import GetFullChannelRequest
from telethon.tl.types import (
    Channel,
    MessageMediaDocument,
    MessageMediaPhoto,
    MessageMediaWebPage,
    PeerChannel,
)

logger = logging.getLogger(__name__)

_RETRY_DELAYS: list[float] = [1.0, 2.0, 4.0]
_FLOOD_WAIT_BUFFER: float = 5.0


class TelegramParser:
    """Wraps a :class:`TelegramClient` with retry and error-handling helpers.

    Args:
        api_id: Telegram application API ID.
        api_hash: Telegram application API hash.
        session_name: Path/name of the Telethon session file.
    """

    def __init__(self, api_id: int, api_hash: str, session_name: str = "tg_session") -> None:
        self._api_id = api_id
        self._api_hash = api_hash
        self._session_name = session_name
        self._client: TelegramClient | None = None

    async def connect(self) -> None:
        """Create and connect the Telegram client, reusing an existing session."""
        self._client = TelegramClient(self._session_name, self._api_id, self._api_hash)
        await self._client.connect()
        if not await self._client.is_user_authorized():
            logger.warning(
                "Telegram session '%s' is not authorised. "
                "Run an interactive script once to authenticate.",
                self._session_name,
            )

    async def disconnect(self) -> None:
        """Disconnect the Telegram client gracefully."""
        if self._client and self._client.is_connected():
            await self._client.disconnect()
            logger.debug("Telegram client disconnected.")

    async def get_channel_info(self, username: str) -> dict[str, Any] | None:
        """Fetch metadata for a public Telegram channel.

        Args:
            username: The channel @username (without the '@').

        Returns:
            A dictionary with channel metadata, or ``None`` if the channel
            cannot be accessed.
        """
        assert self._client is not None, "Call connect() first"

        for attempt, delay in enumerate(_RETRY_DELAYS, start=1):
            try:
                entity = await self._client.get_entity(username)
                if not isinstance(entity, Channel):
                    logger.debug("'%s' is not a Channel entity, skipping.", username)
                    return None

                # Use GetFullChannelRequest — the correct Telethon API for full channel info
                full_channel = await self._client(GetFullChannelRequest(channel=entity))
                full_chat = full_channel.full_chat
                subscribers = getattr(full_chat, "participants_count", None)

                # Avatar URL is not directly available via Telethon without downloading;
                # store a placeholder reference if the channel has a photo.
                has_photo = entity.photo is not None
                avatar_url: str | None = (
                    f"tg://channel/{entity.id}/photo" if has_photo else None
                )

                return {
                    "channel_id": entity.id,
                    "username": entity.username,
                    "title": entity.title,
                    "description": getattr(full_chat, "about", None),
                    "subscribers_count": subscribers,
                    "avatar_url": avatar_url,
                    "is_verified": getattr(entity, "verified", False),
                    "is_scam": getattr(entity, "scam", False),
                }

            except FloodWaitError as exc:
                wait_time = exc.seconds + _FLOOD_WAIT_BUFFER
                logger.warning(
                    "FloodWaitError for '%s': waiting %.0f seconds...", username, wait_time
                )
                await asyncio.sleep(wait_time)
                # After waiting, retry immediately (don't count as a regular retry)
                continue

            except (ChannelPrivateError, UsernameNotOccupiedError) as exc:
                logger.info("Skipping '%s': %s", username, exc)
                return None

            except Exception as exc:
                logger.warning(
                    "Attempt %d/%d for '%s' failed: %s",
                    attempt,
                    len(_RETRY_DELAYS),
                    username,
                    exc,
                )
                if attempt < len(_RETRY_DELAYS):
                    await asyncio.sleep(delay)
                else:
                    logger.error("All retries exhausted for '%s'.", username)
                    return None

        return None

    async def get_channel_posts(
        self, channel: dict[str, Any], limit: int
    ) -> list[dict[str, Any]]:
        """Fetch the most recent posts from a channel.

        Args:
            channel: Channel info dict as returned by :meth:`get_channel_info`.
            limit: Maximum number of posts to retrieve.

        Returns:
            List of post data dictionaries.
        """
        assert self._client is not None, "Call connect() first"

        channel_id: int = channel["channel_id"]
        posts: list[dict[str, Any]] = []

        for attempt, delay in enumerate(_RETRY_DELAYS, start=1):
            try:
                peer = PeerChannel(channel_id)
                async for message in self._client.iter_messages(peer, limit=limit):
                    media_type: str | None = None
                    has_media = message.media is not None

                    if isinstance(message.media, MessageMediaPhoto):
                        media_type = "photo"
                    elif isinstance(message.media, MessageMediaDocument):
                        doc = message.media.document
                        mime = getattr(doc, "mime_type", "")
                        if mime.startswith("video/"):
                            media_type = "video"
                        elif mime.startswith("audio/"):
                            media_type = "audio"
                        else:
                            media_type = "document"
                    elif isinstance(message.media, MessageMediaWebPage):
                        media_type = "webpage"
                        has_media = False  # treat web previews as no media

                    reactions_count = 0
                    if message.reactions:
                        for result in message.reactions.results:
                            reactions_count += result.count

                    posts.append(
                        {
                            "message_id": message.id,
                            "channel_id": channel_id,
                            "text": message.text,
                            "published_at": message.date,
                            "views": message.views or 0,
                            "forwards": message.forwards or 0,
                            "replies_count": (
                                message.replies.replies if message.replies else 0
                            ),
                            "reactions_count": reactions_count,
                            "has_media": has_media,
                            "media_type": media_type,
                        }
                    )
                return posts

            except FloodWaitError as exc:
                wait_time = exc.seconds + _FLOOD_WAIT_BUFFER
                logger.warning(
                    "FloodWaitError fetching posts for channel %d: waiting %.0f seconds...",
                    channel_id,
                    wait_time,
                )
                await asyncio.sleep(wait_time)
                continue

            except (ChannelPrivateError,) as exc:
                logger.info("Cannot fetch posts for channel %d: %s", channel_id, exc)
                return []

            except Exception as exc:
                logger.warning(
                    "Attempt %d/%d fetching posts for channel %d failed: %s",
                    attempt,
                    len(_RETRY_DELAYS),
                    channel_id,
                    exc,
                )
                if attempt < len(_RETRY_DELAYS):
                    await asyncio.sleep(delay)
                else:
                    logger.error(
                        "All retries exhausted fetching posts for channel %d.", channel_id
                    )
                    return []

        return posts
