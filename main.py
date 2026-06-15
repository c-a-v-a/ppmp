"""Main entry point for the PPMP secure messaging client application."""

import asyncio
import logging
import sys

from ppmp.cli import interface as cli
from ppmp.state.state_machine import StateMachine


def configure_logging() -> None:
    """Configures global logging settings for the application.

    Logs are written to a local file named 'ppmp_debug.log' using an explicitly 
    defined format and UTF-8 encoding.
    """

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler("ppmp_debug.log", encoding="utf-8"),
        ],
    )


async def main() -> None:
    """Orchestrates application startup, initialization wizard, and the main task loop."""

    configure_logging()

    try:
        startup_config = await cli.run_startup_wizard()

        cli.print_separator()

        state_machine = StateMachine(startup_config)

        await state_machine.start()

        cli.print_status("Application finished successfully. Goodbye!")

    except KeyboardInterrupt:
        print("\n[!] Program execution was interrupted by the user.")
    except Exception as e:
        print(f"\n[!] Critical error during execution: {e}", file=sys.stderr)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass