"""Base frame class providing JSON and dictionary serialization utilities."""

from dataclasses import asdict
import json
from typing import Any, TypeVar

from frame_type import FrameType


T = TypeVar("T", bound="Frame")


class Frame:
    """Base class for all message frames.

    Provides serialization and deserialization methods for converting frame
    instances to and from dictionaries and JSON strings.

    Attributes:
        frame_type: The type identifier associated with the frame.
        timestamp: Timestamp indicating when the frame was sent.
    """

    frame_type: FrameType
    timestamp: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> T:
        """Creates an instance of the class from a dictionary.

        Args:
            data: Dictionary containing the data used to initialize the
                instance.

        Returns:
            An instance of the class initialized with the provided data.
        """
        return cls(**data)

    @classmethod
    def from_json(cls, json_str: str) -> T:
        """Creates an instance of the class from a JSON string.

        Args:
            json_str: JSON-encoded string containing the data used to
                initialize the instance.

        Returns:
            An instance of the class initialized with the decoded JSON data.
        """
        data = json.loads(json_str)
        return cls.from_dict(data)

    def to_dict(self) -> dict[str, Any]:
        """Serializes the instance to a dictionary.

        Returns:
            A dictionary representation of the instance.
        """
        return asdict(self)

    def to_json(self) -> str:
        """Serializes the instance to a JSON string.

        Returns:
            A JSON-encoded string representation of the instance.
        """
        return json.dumps(self.to_dict())