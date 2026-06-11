"""Message payload definitions."""

from dataclasses import dataclass


class MessagePayload():
    """Encrypted message payload.

    Contains the encrypted message data and the cryptographic parameters
    required for decryption and authentication. This payload is used by
    the ``MessageFrame`` class.

    Attributes:
        nonce: Nonce used during encryption.
        ciphertext: Encrypted message data.
        auth_tag: Authentication tag used to verify message integrity and
            authenticity.
    """
    nonce: str
    ciphertext: str
    auth_tag: str