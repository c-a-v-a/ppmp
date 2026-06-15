"""Symmetric messaging encryption and decryption module using AES-GCM."""

import os
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from ..data.message_payload import MessagePayload
from .utils import b64_to_bytes, bytes_to_b64


def encrypt_message(session_key: bytes, plaintext: str) -> MessagePayload:
    """Encrypts a plaintext string using AES-GCM with a random 12-byte nonce.

    Args:
        session_key: A 256-bit symmetric key used for the AESGCM block cipher.
        plaintext: The raw UTF-8 string message to encrypt.

    Returns:
        A MessagePayload data class holding the Base64 UTF-8 string segments
        of the nonce, ciphertext, and 16-byte authentication tag.
    """

    aesgcm = AESGCM(session_key)
    nonce = os.urandom(12)  # 12 bytes is the standard safe default for GCM nonces
    plaintext_bytes = plaintext.encode("utf-8")

    # Cryptography returns ciphertext combined with the 16-byte authentication tag
    encrypted_data = aesgcm.encrypt(nonce, plaintext_bytes, None)

    ciphertext = encrypted_data[:-16]
    auth_tag = encrypted_data[-16:]

    return MessagePayload(
        bytes_to_b64(nonce), bytes_to_b64(ciphertext), bytes_to_b64(auth_tag)
    )


def decrypt_message(session_key: bytes, payload: MessagePayload) -> str:
    """Decrypts and verifies an authenticated AES-GCM payload wrapper.

    Args:
        session_key: A 256-bit symmetric key corresponding to the encryption key.
        payload: A MessagePayload instance containing the Base64-encoded nonce,
            ciphertext, and authentication tag components.

    Returns:
        The decrypted, authenticated message decoded back into a UTF-8 string.

    Raises:
        ValueError: If the authentication tag validation fails (indicating data
            tampering/integrity corruption) or if any unexpected formatting 
            decoding errors occur.
    """

    try:
        aesgcm = AESGCM(session_key)
        nonce = b64_to_bytes(payload.nonce)
        ciphertext = b64_to_bytes(payload.ciphertext)
        auth_tag = b64_to_bytes(payload.auth_tag)
        encrypted_data = ciphertext + auth_tag
        decrypted_bytes = aesgcm.decrypt(nonce, encrypted_data, None)
        
        return decrypted_bytes.decode("utf-8")
    except InvalidTag:
        raise ValueError("Integrity error: Message authentication failed.")
    except Exception as e:
        raise ValueError(f"Decryption error occurred: {str(e)}")