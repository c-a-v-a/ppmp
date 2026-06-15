"""Acknowledgment frame definitions."""

from dataclasses import dataclass

from .frame import Frame


@dataclass
class AckFrame(Frame):
    """Frame acknowledging receipt of a message.

    Attributes:
        ack_id: Identifier of the message being acknowledged.
    """

    ack_id: str