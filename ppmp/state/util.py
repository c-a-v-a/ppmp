"""Module for parsing incoming network frames from JSON data."""

import json

from ..data import (
    Frame, HelloFrame, MessageFrame, AckFrame, 
    PingFrame, PongFrame, ByeFrame, ErrorFrame, FrameType
)

def parse_incoming_frame(raw_json: str) -> Frame:
    """Parses a raw JSON string into its corresponding Frame object.

    Args:
        raw_json: A string containing the raw JSON payload to be parsed.

    Returns:
        An instance of a Frame subclass (e.g., HelloFrame, MessageFrame) 
        corresponding to the frame type specified in the JSON data.

    Raises:
        ValueError: If the 'frame_type' in the JSON does not match any 
            known FrameType.
        json.JSONDecodeError: If the provided raw_json string is not 
            valid JSON.
    """
    parsed_dict = json.loads(raw_json)
    raw_type = parsed_dict.get("frame_type")

    match raw_type:
        case FrameType.HELLO:
            return HelloFrame.from_dict(parsed_dict)
        case FrameType.MSG:
            return MessageFrame.from_dict(parsed_dict)
        case FrameType.ACK:
            return AckFrame.from_dict(parsed_dict)
        case FrameType.PING:
            return PingFrame.from_dict(parsed_dict)
        case FrameType.PONG:
            return PongFrame.from_dict(parsed_dict)
        case FrameType.BYE:
            return ByeFrame.from_dict(parsed_dict)
        case FrameType.ERROR:
            return ErrorFrame.from_dict(parsed_dict)
        case _:
            raise ValueError(f"Incorrect frame type: {raw_type}")