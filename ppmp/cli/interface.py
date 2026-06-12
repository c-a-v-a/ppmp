"""
CLI Module for PPMP.

Responsible for:
- Asynchronous, non-blocking keyboard input (user types while messages arrive)
- Rendering incoming messages on screen without corrupting the input prompt
- Parsing user commands (e.g. /exit, /help)
- Providing a clean startup wizard (mode selection, address, port)

Design notes
────────────
asyncio is used throughout so that the receive loop (run by the State Machine)
and the input loop (run here) can coexist in one thread without blocking each
other.  The trick for "concurrent input + output" on a plain terminal is to
print the incoming message, then re-print the prompt.  This is intentionally
simple (no curses/textual dependency) to keep the MVP lean.
"""

import asyncio
import sys
from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional

# ── Constants ────────────────────────────────────────────────────────────────

PROMPT = "> "
CMD_EXIT = "/exit"
CMD_HELP = "/help"

HELP_TEXT = f"""\
┌─ PPMP Commands ──────────────────────────────────────────┐
│  {CMD_EXIT:<20}  Disconnect and quit               │
│  {CMD_HELP:<20}  Show this help message            │
│  <any other text>     Send as an encrypted message       │
└──────────────────────────────────────────────────────────┘"""

BANNER = """\
╔══════════════════════════════════════════════════════════╗
║           PPMP – Peer-to-Peer Message Protocol           ║
║          Secure, end-to-end encrypted CLI chat           ║
╚══════════════════════════════════════════════════════════╝"""

SEPARATOR = "─" * 60


# ── Startup configuration ────────────────────────────────────────────────────

class PeerMode(Enum):
    CALLER = auto()    # initiates the connection
    LISTENER = auto()  # waits for an incoming connection


@dataclass
class StartupConfig:
    mode: PeerMode
    host: Optional[str]   # only relevant for CALLER
    port: int


async def run_startup_wizard() -> StartupConfig:
    """
    Interactive wizard printed at application start.
    Returns the user's chosen mode, host and port.
    """
    _print_banner()

    mode = await _ask_mode()

    if mode == PeerMode.LISTENER:
        port = await _ask_port(default=9999)
        return StartupConfig(mode=mode, host=None, port=port)
    else:
        host = await _ask_host()
        port = await _ask_port(default=9999)
        return StartupConfig(mode=mode, host=host, port=port)


# ── Public rendering helpers ─────────────────────────────────────────────────

def print_info(text: str) -> None:
    """Print a system/informational message, then re-draw the prompt."""
    _clear_prompt()
    print(f"[*] {text}")
    _redraw_prompt()


def print_error(text: str) -> None:
    """Print an error message."""
    _clear_prompt()
    print(f"[!] {text}", file=sys.stderr)
    _redraw_prompt()


def print_message(sender: str, text: str) -> None:
    """
    Render an incoming message.

    Clears the current prompt line so the message appears cleanly above it,
    then re-draws the prompt so the user can keep typing.
    """
    _clear_prompt()
    print(f"[{sender}] {text}")
    _redraw_prompt()


def print_own_message(text: str) -> None:
    """Echo the user's own sent message in a distinct style."""
    # Already echoed by the terminal; we just add the visual tag.
    # Move up one line to overwrite the raw echo, then print styled.
    sys.stdout.write("\033[1A\033[2K")   # up one line, erase it
    print(f"[you] {text}")
    _redraw_prompt()


def print_status(text: str) -> None:
    """Print a connection-status change (connect / disconnect)."""
    _clear_prompt()
    print(f"\n{SEPARATOR}")
    print(f"  {text}")
    print(f"{SEPARATOR}\n")
    _redraw_prompt()


def print_separator() -> None:
    _clear_prompt()
    print(SEPARATOR)
    _redraw_prompt()


# ── Async input loop ─────────────────────────────────────────────────────────

class UserCommand(Enum):
    MESSAGE = auto()
    EXIT = auto()
    HELP = auto()
    UNKNOWN = auto()


@dataclass
class UserInput:
    command: UserCommand
    text: str = ""


async def read_user_input() -> UserInput:
    """
    Asynchronously read one line of user input.

    Uses asyncio's default executor so the blocking ``sys.stdin.readline``
    call does not stall the event loop (and thus the receive loop).
    """
    loop = asyncio.get_running_loop()
    sys.stdout.write(PROMPT)
    sys.stdout.flush()

    raw: str = await loop.run_in_executor(None, sys.stdin.readline)
    text = raw.rstrip("\n")

    if text == CMD_EXIT:
        return UserInput(command=UserCommand.EXIT, text=text)
    if text == CMD_HELP:
        return UserInput(command=UserCommand.HELP, text=text)
    if text.startswith("/"):
        return UserInput(command=UserCommand.UNKNOWN, text=text)
    return UserInput(command=UserCommand.MESSAGE, text=text)


async def input_loop(
    on_message: "asyncio.Queue[str]",
    on_exit: "asyncio.Event",
) -> None:
    """
    Main input loop.  Reads lines until the user types ``/exit`` or EOF.

    Parameters
    ----------
    on_message:
        An asyncio Queue into which outgoing message strings are placed.
        Consumers (State Machine) should await ``on_message.get()``.
    on_exit:
        An asyncio Event that is set when the user requests a disconnect.
    """
    while not on_exit.is_set():
        try:
            user_input = await read_user_input()
        except EOFError:
            # Ctrl-D / pipe closed
            on_exit.set()
            break

        match user_input.command:
            case UserCommand.EXIT:
                print_info("Disconnecting …")
                on_exit.set()

            case UserCommand.HELP:
                _clear_prompt()
                print(HELP_TEXT)
                _redraw_prompt()

            case UserCommand.UNKNOWN:
                print_error(f"Unknown command: {user_input.text!r}. Type /help.")

            case UserCommand.MESSAGE:
                if user_input.text.strip():
                    await on_message.put(user_input.text)
                    print_own_message(user_input.text)


# ── Internal helpers ─────────────────────────────────────────────────────────

def _print_banner() -> None:
    print(BANNER)
    print()


def _clear_prompt() -> None:
    """Erase the current prompt line so we can print above it cleanly."""
    sys.stdout.write("\r\033[2K")
    sys.stdout.flush()


def _redraw_prompt() -> None:
    """Re-draw the input prompt after printing a message."""
    sys.stdout.write(PROMPT)
    sys.stdout.flush()


async def _ask_mode() -> PeerMode:
    loop = asyncio.get_running_loop()
    while True:
        print("  Start as:")
        print("    [1] Listener  – wait for an incoming connection")
        print("    [2] Caller    – connect to a remote peer")
        sys.stdout.write("  Choice [1/2]: ")
        sys.stdout.flush()
        raw = (await loop.run_in_executor(None, sys.stdin.readline)).strip()
        if raw == "1":
            return PeerMode.LISTENER
        if raw == "2":
            return PeerMode.CALLER
        print("  Please enter 1 or 2.\n")


async def _ask_host() -> str:
    loop = asyncio.get_running_loop()
    while True:
        sys.stdout.write("  Remote host (IP or hostname): ")
        sys.stdout.flush()
        raw = (await loop.run_in_executor(None, sys.stdin.readline)).strip()
        if raw:
            return raw
        print("  Host cannot be empty.")


async def _ask_port(default: int = 9999) -> int:
    loop = asyncio.get_running_loop()
    while True:
        sys.stdout.write(f"  Port [{default}]: ")
        sys.stdout.flush()
        raw = (await loop.run_in_executor(None, sys.stdin.readline)).strip()
        if not raw:
            return default
        try:
            port = int(raw)
            if 1 <= port <= 65535:
                return port
        except ValueError:
            pass
        print("  Enter a valid port number (1–65535).")
