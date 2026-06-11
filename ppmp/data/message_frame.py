"""Message frame definitions."""

from dataclasses import dataclass

from frame import Frame
from message_payload import MessagePayload


@dataclass
class HelloFrame(Frame):
    """Frame containing an encrypted message.

    Attributes:
        msg_id: Unique identifier of the message.
        sender_id: Unique identifier of the sender.
        payload: Encrypted message payload.
    """
    msg_id: str
    sender_id: str
    payload: MessagePayload
