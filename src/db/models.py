"""SQLAlchemy ORM models for the Telegram channel parser."""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    VARCHAR,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.sql import func
from sqlalchemy.types import TIMESTAMP


class Base(DeclarativeBase):
    """Base class for all ORM models."""

    pass


class Channel(Base):
    """Represents a Telegram channel stored in the `channels` table."""

    __tablename__ = "channels"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    channel_id = Column(BigInteger, unique=True, nullable=False, comment="Telegram channel ID")
    username = Column(VARCHAR(255), nullable=True, comment="@username of the channel")
    title = Column(Text, nullable=True, comment="Channel title")
    description = Column(Text, nullable=True, comment="Channel bio/description")
    subscribers_count = Column(Integer, nullable=True, comment="Subscribers count")
    avatar_url = Column(Text, nullable=True, comment="URL of channel avatar if available")
    is_verified = Column(Boolean, default=False, server_default="false", nullable=False)
    is_scam = Column(Boolean, default=False, server_default="false", nullable=False)
    created_at = Column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at = Column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<Channel id={self.channel_id} username={self.username!r}>"


class Post(Base):
    """Represents a Telegram post stored in the `posts` table."""

    __tablename__ = "posts"
    __table_args__ = (
        UniqueConstraint("channel_id", "message_id", name="uq_posts_channel_message"),
        Index("idx_posts_channel_id", "channel_id"),
        Index("idx_posts_published_at", "published_at"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    message_id = Column(BigInteger, nullable=False, comment="Telegram message ID")
    channel_id = Column(
        BigInteger,
        nullable=False,
        comment="Foreign key referencing channels.channel_id",
    )
    text = Column(Text, nullable=True, comment="Post text content")
    published_at = Column(TIMESTAMP(timezone=True), nullable=True, comment="Publication timestamp")
    views = Column(Integer, default=0, server_default="0", nullable=False)
    forwards = Column(Integer, default=0, server_default="0", nullable=False)
    replies_count = Column(Integer, default=0, server_default="0", nullable=False)
    reactions_count = Column(Integer, default=0, server_default="0", nullable=False)
    has_media = Column(Boolean, default=False, server_default="false", nullable=False)
    media_type = Column(VARCHAR(50), nullable=True, comment="Media type: photo, video, document, etc.")
    created_at = Column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at = Column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<Post channel_id={self.channel_id} message_id={self.message_id}>"


# Expose datetime for type hints in other modules
__all__ = ["Base", "Channel", "Post", "datetime"]
