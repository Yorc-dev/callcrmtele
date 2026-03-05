"""Configuration module for the Telegram channel parser."""

import argparse
import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()


@dataclass
class Config:
    """Application configuration loaded from environment variables or .env file."""

    # Telegram API credentials
    tg_api_id: int = field(default_factory=lambda: int(os.environ.get("TG_API_ID", "0")))
    tg_api_hash: str = field(default_factory=lambda: os.environ.get("TG_API_HASH", ""))
    tg_session_name: str = field(default_factory=lambda: os.environ.get("TG_SESSION_NAME", "tg_session"))

    # PostgreSQL connection parameters
    db_host: str = field(default_factory=lambda: os.environ.get("DB_HOST", "localhost"))
    db_port: int = field(default_factory=lambda: int(os.environ.get("DB_PORT", "5432")))
    db_name: str = field(default_factory=lambda: os.environ.get("DB_NAME", "telegram_parser"))
    db_user: str = field(default_factory=lambda: os.environ.get("DB_USER", "postgres"))
    db_password: str = field(default_factory=lambda: os.environ.get("DB_PASSWORD", ""))

    # Parser settings
    channels_limit: int = field(default_factory=lambda: int(os.environ.get("CHANNELS_LIMIT", "1000")))
    posts_limit: int = field(default_factory=lambda: int(os.environ.get("POSTS_LIMIT", "10")))

    @property
    def db_url(self) -> str:
        """Build async PostgreSQL connection URL."""
        return (
            f"postgresql+asyncpg://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    def validate(self) -> None:
        """Validate that all required fields are present."""
        if not self.tg_api_id:
            raise ValueError("TG_API_ID environment variable is required")
        if not self.tg_api_hash:
            raise ValueError("TG_API_HASH environment variable is required")
        if not self.db_password:
            raise ValueError("DB_PASSWORD environment variable is required")


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments for overriding config values."""
    parser = argparse.ArgumentParser(
        description="Telegram channel parser — collects posts and channel info into PostgreSQL."
    )
    parser.add_argument(
        "--channels-limit",
        type=int,
        default=None,
        help="Number of channels to parse (overrides CHANNELS_LIMIT env var)",
    )
    parser.add_argument(
        "--posts-limit",
        type=int,
        default=None,
        help="Number of posts per channel (overrides POSTS_LIMIT env var)",
    )
    return parser.parse_args()


def get_config() -> Config:
    """Create Config instance and apply CLI argument overrides."""
    cfg = Config()
    args = parse_args()
    if args.channels_limit is not None:
        cfg.channels_limit = args.channels_limit
    if args.posts_limit is not None:
        cfg.posts_limit = args.posts_limit
    return cfg
