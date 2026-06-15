"""Message frame definitions."""

from dataclasses import dataclass, asdict
from typing import Any

from .frame import Frame
from .message_payload import MessagePayload


@dataclass
class MessageFrame(Frame):
    """Frame containing an encrypted message.

    Attributes:
        msg_id: Unique identifier of the message.
        sender_id: Unique identifier of the sender.
        payload: Encrypted message payload.
    """
    msg_id: str
    sender_id: str
    payload: MessagePayload

    @classmethod
    def from_dict(cls, data: dict[str, Any]):
        """Creates an instance of the class from a dictionary.

        Args:
            data: Dictionary containing the data used to initialize the
                instance.

        Returns:
            An instance of the MessageFrame class.
        """
        data_copy = data.copy()
        
        if isinstance(data_copy.get("payload"), dict):
            data_copy["payload"] = MessagePayload(**data_copy["payload"])
            
        return cls(**data_copy)

    def to_dict(self) -> dict[str, Any]:
        """Serializes the instance to a dictionary.

        Returns:
            A dictionary representation of the instance.
        """
        return asdict(self)