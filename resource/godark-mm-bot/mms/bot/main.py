#!/usr/bin/env python3
"""Run the vanilla GoDark MM bot."""

from __future__ import annotations

import asyncio
import logging
import signal

from bot import VanillaMMBot
from config import BotConfig


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )
    config = BotConfig.from_env()
    bot = VanillaMMBot(config)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, bot.stop)

    try:
        loop.run_until_complete(bot.run())
    finally:
        loop.close()


if __name__ == "__main__":
    main()
