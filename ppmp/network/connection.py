"""
Network Layer Module for PPMP.

Responsible for:
- Low-level TCP socket management (connect / listen / accept)
- Frame-based I/O: each message is a UTF-8 JSON line terminated by '\\n'
- Enforcing the 64 KB per-frame size limit
- Detecting connection loss and exposing it to higher layers
- Thread-safe async-style receive loop via asyncio streams
"""

import asyncio
import logging
from typing import Callable, Optional

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────────────

MAX_FRAME_BYTES: int = 65_536          # 64 KiB hard limit (spec §5 non-functional)
FRAME_DELIMITER: bytes = b"\n"
DEFAULT_PORT: int = 9999
RECONNECT_DELAYS: tuple[int, ...] = (5, 15, 60)   # seconds, spec UC5


# ── Exceptions ───────────────────────────────────────────────────────────────

class NetworkError(Exception):
    """Raised for unrecoverable network-level errors."""


class FrameTooLargeError(NetworkError):
    """Raised when an incoming frame exceeds MAX_FRAME_BYTES."""


class ConnectionLostError(NetworkError):
    """Raised when the remote peer closes the TCP connection."""


# ── Connection abstraction ───────────────────────────────────────────────────

class PPMPConnection:
    """
    Wraps an asyncio StreamReader/StreamWriter pair and provides
    PPMP frame-level read/write operations.

    All I/O uses UTF-8 JSON lines (terminated by '\\n').
    """

    def __init__(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        self._reader = reader
        self._writer = writer
        self._closed = False
        peer = writer.get_extra_info("peername")
        self.remote_address: tuple[str, int] = peer if peer else ("?", 0)
        logger.info("Connection established with %s:%s", *self.remote_address)

    # ── Send ─────────────────────────────────────────────────────────────────

    async def send_frame(self, raw_json: str) -> None:
        """
        Serialise *raw_json* as a UTF-8 line and write it to the TCP stream.

        Raises:
            FrameTooLargeError: if the encoded frame exceeds MAX_FRAME_BYTES.
            ConnectionLostError: if the socket is already closed.
        """
        if self._closed:
            raise ConnectionLostError("Cannot send on a closed connection.")

        encoded = (raw_json.rstrip("\n") + "\n").encode("utf-8")
        if len(encoded) > MAX_FRAME_BYTES:
            raise FrameTooLargeError(
                f"Outgoing frame size {len(encoded)} exceeds limit {MAX_FRAME_BYTES}."
            )

        try:
            self._writer.write(encoded)
            await self._writer.drain()
            logger.debug("→ %d bytes sent", len(encoded))
        except (BrokenPipeError, ConnectionResetError, OSError) as exc:
            self._closed = True
            raise ConnectionLostError(f"Send failed: {exc}") from exc

    # ── Receive ──────────────────────────────────────────────────────────────

    async def recv_frame(self) -> str:
        """
        Read exactly one '\\n'-terminated frame from the stream.

        Returns:
            The frame content as a UTF-8 string (newline stripped).

        Raises:
            FrameTooLargeError: if the frame exceeds MAX_FRAME_BYTES.
            ConnectionLostError: if the peer closed the connection cleanly.
        """
        if self._closed:
            raise ConnectionLostError("Cannot receive on a closed connection.")

        try:
            raw = await self._reader.readuntil(FRAME_DELIMITER)
        except asyncio.IncompleteReadError as exc:
            self._closed = True
            raise ConnectionLostError("Remote peer closed the connection.") from exc
        except asyncio.LimitOverrunError as exc:
            # Buffer limit hit before delimiter — frame is too large.
            self._closed = True
            raise FrameTooLargeError(
                f"Incoming frame exceeds {MAX_FRAME_BYTES} bytes."
            ) from exc
        except (ConnectionResetError, OSError) as exc:
            self._closed = True
            raise ConnectionLostError(f"Receive failed: {exc}") from exc

        if len(raw) > MAX_FRAME_BYTES:
            self._closed = True
            raise FrameTooLargeError(
                f"Incoming frame size {len(raw)} exceeds limit {MAX_FRAME_BYTES}."
            )

        decoded = raw.rstrip(b"\n").decode("utf-8")
        logger.debug("← %d bytes received", len(raw))
        return decoded

    # ── Lifecycle ────────────────────────────────────────────────────────────

    def is_closed(self) -> bool:
        return self._closed

    async def close(self) -> None:
        """Gracefully shut down the TCP socket."""
        if self._closed:
            return
        self._closed = True
        try:
            self._writer.close()
            await self._writer.wait_closed()
        except OSError:
            pass
        logger.info("Connection to %s:%s closed.", *self.remote_address)


# ── Server (Listener peer) ────────────────────────────────────────────────────

class PPMPServer:
    """
    Listens on a TCP port and accepts exactly one incoming connection
    (MVP scope: single active connection at a time).

    Usage::

        server = PPMPServer(port=9999, on_connect=handle_connection)
        await server.start()
        # ...
        await server.stop()
    """

    def __init__(
        self,
        on_connect: Callable[["PPMPConnection"], None],
        host: str = "0.0.0.0",
        port: int = DEFAULT_PORT,
    ) -> None:
        self._on_connect = on_connect
        self.host = host
        self.port = port
        self._server: Optional[asyncio.AbstractServer] = None

    async def start(self) -> None:
        """Start listening for incoming TCP connections."""
        self._server = await asyncio.start_server(
            self._handle_client,
            host=self.host,
            port=self.port,
            limit=MAX_FRAME_BYTES + 1,   # asyncio buffer limit
        )
        logger.info("PPMP server listening on %s:%d", self.host, self.port)

    async def _handle_client(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        conn = PPMPConnection(reader, writer)
        try:
            await self._on_connect(conn)
        except Exception as exc:  # noqa: BLE001
            logger.error("Unhandled error in client handler: %s", exc)
        finally:
            await conn.close()

    async def stop(self) -> None:
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            logger.info("PPMP server stopped.")


# ── Client (Caller peer) ──────────────────────────────────────────────────────

async def connect(
    host: str,
    port: int = DEFAULT_PORT,
    timeout: float = 10.0,
) -> PPMPConnection:
    """
    Open a TCP connection to *host*:*port* and return a :class:`PPMPConnection`.

    Raises:
        NetworkError: if the connection cannot be established within *timeout* seconds.
    """
    logger.info("Connecting to %s:%d …", host, port)
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port, limit=MAX_FRAME_BYTES + 1),
            timeout=timeout,
        )
    except asyncio.TimeoutError as exc:
        raise NetworkError(
            f"Connection to {host}:{port} timed out after {timeout}s."
        ) from exc
    except OSError as exc:
        raise NetworkError(f"Cannot connect to {host}:{port}: {exc}") from exc

    return PPMPConnection(reader, writer)


# ── Reconnect helper ──────────────────────────────────────────────────────────

async def connect_with_retry(
    host: str,
    port: int = DEFAULT_PORT,
    timeout: float = 10.0,
    delays: tuple[int, ...] = RECONNECT_DELAYS,
) -> PPMPConnection:
    """
    Attempt to connect; on failure retry after *delays* seconds (spec UC5).

    Example: delays=(5, 15, 60) → tries at t=0, t+5, t+20, t+80.
    After exhausting all delays, the last :class:`NetworkError` is re-raised.
    """
    last_exc: Optional[Exception] = None
    attempts = [0] + list(delays)      # first attempt is immediate

    for wait in attempts:
        if wait:
            logger.info("Retrying connection in %d s …", wait)
            await asyncio.sleep(wait)
        try:
            return await connect(host, port, timeout)
        except NetworkError as exc:
            last_exc = exc
            logger.warning("Connection attempt failed: %s", exc)

    raise NetworkError(
        f"All connection attempts to {host}:{port} exhausted."
    ) from last_exc
