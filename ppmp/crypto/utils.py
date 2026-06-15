"""Utility module for converting data between bytes and Base64 encoded strings."""

import base64


def bytes_to_b64(data: bytes) -> str:
    """Encodes raw binary data into a Base64 ASCII string representation.

    Args:
        data: The raw bytes payload to be encoded.

    Returns:
        A UTF-8 string containing the Base64 encoded representation of the input.
    """

    return base64.b64encode(data).decode("utf-8")


def b64_to_bytes(data_str: str) -> bytes:
    """Decodes a Base64 encoded string back into its original binary format.

    Args:
        data_str: A UTF-8 string containing Base64 encoded data.

    Returns:
        The decoded raw bytes.

    Raises:
        binascii.Error: If the input string is incorrectly padded or contains
            non-base64 alphabet characters.
    """

    return base64.b64decode(data_str.encode("utf-8"))