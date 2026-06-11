"""Bye frame definitions."""

from dataclasses import dataclass

from frame import Frame


@dataclass
class ByeFrame(Frame):
    """Frame indicating termination of a session.

    Attributes:
        reason: Human-readable reason for closing the session.
        sig: Digital signature verifying the frame authenticity.
    """

    reason: str
    sig: str