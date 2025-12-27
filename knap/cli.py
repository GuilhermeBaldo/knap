"""CLI interface for Knap - interact with your Obsidian vault from the terminal."""

import argparse
import asyncio
import logging
import sys

from knap.agent import Agent
from knap.agent.core import Colors
from knap.config import get_settings

# CLI user ID (used for conversation history)
CLI_USER_ID = 0


def setup_logging() -> None:
    """Configure logging for CLI."""
    logging.basicConfig(
        format="%(message)s",
        level=logging.INFO,
    )
    # Reduce noise from libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)


def print_response(text: str) -> None:
    """Print agent response with formatting."""
    print(f"\n{Colors.BOLD}{Colors.MAGENTA}Knap:{Colors.RESET} {text}\n")


async def process_single_message(agent: Agent, message: str) -> None:
    """Process a single message and print the response."""
    response = await agent.process_message(CLI_USER_ID, message)

    if response.pending_confirmations:
        print(f"\n{Colors.YELLOW}Pending confirmations:{Colors.RESET}")
        for conf in response.pending_confirmations:
            print(f"  - {conf.message}")
            # Auto-confirm in CLI mode (user can see the action in logs)
            result = agent.execute_confirmed(conf.confirmation_id)
            if result:
                print(f"    {Colors.GREEN}✓ {result}{Colors.RESET}")

    if response.pending_plan:
        print(f"\n{Colors.CYAN}Plan created: {response.pending_plan.title}{Colors.RESET}")
        print("Use 'approve' to execute or 'reject' to cancel.")


async def interactive_mode(agent: Agent) -> None:
    """Run interactive REPL mode."""
    print(f"{Colors.GREEN}{Colors.BOLD}Knap CLI{Colors.RESET}")
    print(
        f"{Colors.DIM}Type your message and press Enter. Use 'exit' or Ctrl+C to quit.{Colors.RESET}"
    )
    print(
        f"{Colors.DIM}Commands: /clear (clear history), /refresh (refresh index), /help{Colors.RESET}"
    )
    print()

    pending_plan = None

    while True:
        try:
            # Read user input
            user_input = input(f"{Colors.BOLD}{Colors.BLUE}You:{Colors.RESET} ").strip()

            if not user_input:
                continue

            # Handle special commands
            if user_input.lower() in ("exit", "quit", "/exit", "/quit"):
                print(f"{Colors.DIM}Goodbye!{Colors.RESET}")
                break

            if user_input.lower() in ("/clear", "/reset"):
                agent.clear_history(CLI_USER_ID)
                print(f"{Colors.GREEN}Conversation history cleared.{Colors.RESET}")
                continue

            if user_input.lower() == "/refresh":
                print(f"{Colors.DIM}Refreshing vault index...{Colors.RESET}")
                agent.refresh_index()
                print(f"{Colors.GREEN}Vault index refreshed.{Colors.RESET}")
                continue

            if user_input.lower() == "/help":
                print(f"""
{Colors.BOLD}Knap CLI Commands:{Colors.RESET}
  /clear    - Clear conversation history
  /refresh  - Refresh vault index
  /help     - Show this help message
  exit      - Exit the CLI

{Colors.BOLD}Plan Commands:{Colors.RESET}
  approve   - Approve and execute a pending plan
  reject    - Reject a pending plan

Just type your message to interact with your Obsidian vault.
""")
                continue

            # Handle plan approval/rejection
            if user_input.lower() == "approve" and pending_plan:
                agent.approve_plan(pending_plan.plan_id)
                response = await agent.execute_plan(pending_plan)
                print_response(response.text)
                pending_plan = None
                continue

            if user_input.lower() == "reject" and pending_plan:
                agent.reject_plan(pending_plan.plan_id)
                print(f"{Colors.RED}Plan rejected.{Colors.RESET}")
                pending_plan = None
                continue

            # Process message
            response = await agent.process_message(CLI_USER_ID, user_input)

            # Handle pending confirmations (auto-confirm in CLI)
            if response.pending_confirmations:
                print(f"\n{Colors.YELLOW}Executing confirmed actions...{Colors.RESET}")
                for conf in response.pending_confirmations:
                    result = agent.execute_confirmed(conf.confirmation_id)
                    if result:
                        print(f"  {Colors.GREEN}✓ {result}{Colors.RESET}")

            # Handle pending plan
            if response.pending_plan:
                pending_plan = response.pending_plan
                print(
                    f"\n{Colors.CYAN}Type 'approve' to execute or 'reject' to cancel.{Colors.RESET}"
                )

        except KeyboardInterrupt:
            print(f"\n{Colors.DIM}Goodbye!{Colors.RESET}")
            break
        except EOFError:
            print(f"\n{Colors.DIM}Goodbye!{Colors.RESET}")
            break
        except Exception as e:
            print(f"{Colors.RED}Error: {e}{Colors.RESET}")


def cli() -> None:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="knap-cli",
        description="Interact with your Obsidian vault using natural language.",
    )
    parser.add_argument(
        "-m",
        "--message",
        type=str,
        help="Send a single message and exit (non-interactive mode)",
    )
    parser.add_argument(
        "--clear-history",
        action="store_true",
        help="Clear conversation history and exit",
    )
    parser.add_argument(
        "--refresh-index",
        action="store_true",
        help="Refresh the vault index and exit",
    )

    args = parser.parse_args()

    setup_logging()
    logger = logging.getLogger(__name__)

    # Load settings
    try:
        settings = get_settings()
        logger.info(f"{Colors.DIM}Vault: {settings.vault_path}{Colors.RESET}")
    except Exception as e:
        logger.error(f"{Colors.RED}Failed to load settings: {e}{Colors.RESET}")
        logger.error(
            f"{Colors.RED}Make sure you have a .env file with VAULT_PATH and OPENAI_API_KEY.{Colors.RESET}"
        )
        sys.exit(1)

    # Initialize agent
    agent = Agent(settings)

    # Handle utility commands
    if args.clear_history:
        agent.clear_history(CLI_USER_ID)
        print(f"{Colors.GREEN}Conversation history cleared.{Colors.RESET}")
        return

    if args.refresh_index:
        print(f"{Colors.DIM}Refreshing vault index...{Colors.RESET}")
        agent.refresh_index()
        print(f"{Colors.GREEN}Vault index refreshed.{Colors.RESET}")
        return

    # Single message mode
    if args.message:
        asyncio.run(process_single_message(agent, args.message))
        return

    # Interactive mode
    asyncio.run(interactive_mode(agent))


if __name__ == "__main__":
    cli()
