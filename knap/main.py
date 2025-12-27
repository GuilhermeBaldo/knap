"""Main entry point for Knap."""

import logging
import sys

from knap.agent import Agent
from knap.agent.core import Colors
from knap.config import get_settings
from knap.telegram.bot import TelegramBot


def setup_logging() -> None:
    """Configure logging."""
    logging.basicConfig(
        format="%(message)s",
        level=logging.INFO,
    )
    # Reduce noise from libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("telegram").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)


def main() -> None:
    """Run the Knap bot."""
    setup_logging()
    logger = logging.getLogger(__name__)

    try:
        settings = get_settings()
        logger.info(f"{Colors.DIM}Vault: {settings.vault_path}{Colors.RESET}")
        logger.info(f"{Colors.DIM}Users: {settings.allowed_users}{Colors.RESET}")
    except Exception as e:
        logger.error(f"{Colors.RED}Failed to load settings: {e}{Colors.RESET}")
        logger.error(
            f"{Colors.RED}Make sure you have a .env file with required variables.{Colors.RESET}"
        )
        sys.exit(1)

    agent = Agent(settings)
    bot = TelegramBot(settings, agent)

    logger.info(f"{Colors.GREEN}{Colors.BOLD}Knap started ✓{Colors.RESET}")
    bot.run()


if __name__ == "__main__":
    main()
