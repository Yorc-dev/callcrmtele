"""Entry point for the Telegram channel parser.

Usage:
    python parser.py
    python parser.py --channels-limit 500 --posts-limit 5
"""

import asyncio
import logging
import sys

from src.config import get_config
from src.db.database import init_db
from src.parser.channel_parser import ChannelDataCollector
from src.parser.channels_list import CHANNELS

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

logger = logging.getLogger(__name__)


async def main() -> None:
    """Initialise configuration and database, then start the parser."""
    config = get_config()

    try:
        config.validate()
    except ValueError as exc:
        logger.error("Configuration error: %s", exc)
        sys.exit(1)

    logger.info(
        "Parser settings — channels_limit=%d, posts_limit=%d",
        config.channels_limit,
        config.posts_limit,
    )

    await init_db(config.db_url)

    collector = ChannelDataCollector(config)
    stats = await collector.run(CHANNELS)

    print("\n" + "=" * 50)
    print("  Parsing complete — summary")
    print("=" * 50)
    print(f"  Channels processed : {stats['channels_processed']}")
    print(f"  Posts collected    : {stats['posts_collected']}")
    print(f"  Channels skipped   : {stats['channels_skipped']}")
    print(f"  Errors             : {stats['errors']}")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
