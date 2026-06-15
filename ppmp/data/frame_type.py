"""Enumeration of supported message frame types."""

from enum import StrEnum


class FrameType(StrEnum):
    """Enumeration of message frame types."""
    HELLO = "HELLO"
    MSG = "MSG"
    ACK = "ACK"
    PING = "PING"
    PONG = "PONG"
    BYE = "BYE"
    ERROR = "ERROR"