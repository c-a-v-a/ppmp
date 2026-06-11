"""Enumeration of supported message frame types."""

from enum import IntEnum


class FrameType(IntEnum):
    """Enumeration of message frame types."""
    HELLO = 1
    MSG = 2
    ACK = 3
    PING = 4
    PONG = 5
    BYE = 6
    ERROR = 7