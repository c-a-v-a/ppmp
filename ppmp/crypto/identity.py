"""Cryptographic identity module utilizing Ed25519 for digital signatures."""

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric import ed25519

from .utils import b64_to_bytes, bytes_to_b64


def generate_identity() -> ed25519.Ed25519PrivateKey:
    """Generates a new, secure private Ed25519 identity key.

    Returns:
        A freshly generated Ed25519PrivateKey instance.
    """

    return ed25519.Ed25519PrivateKey.generate()


def get_public_key_b64(private_key: ed25519.Ed25519PrivateKey) -> str:
    """Extracts the public key from an Ed25519 private key as a Base64 string.

    Args:
        private_key: The Ed25519PrivateKey instance to derive the public key from.

    Returns:
        The raw public key bytes formatted into a Base64 UTF-8 string.
    """

    pub_bytes = private_key.public_key().public_bytes_raw()
    
    return bytes_to_b64(pub_bytes)


def sign_data(private_key: ed25519.Ed25519PrivateKey, data: bytes) -> str:
    """Signs an arbitrary block of bytes data using an Ed25519 private key.

    Args:
        private_key: The Ed25519PrivateKey instance to sign the data with.
        data: The raw binary data payload to sign.

    Returns:
        The resulting digital signature formatted into a Base64 UTF-8 string.
    """

    signature = private_key.sign(data)

    return bytes_to_b64(signature)


def verify_signature(
    sender_id_b64: str, data: bytes, signature_b64: str
) -> bool:
    """Verifies an Ed25519 digital signature against a Base64 public key ID.

    Args:
        sender_id_b64: The sender's public identity key, encoded as a Base64 
            UTF-8 string.
        data: The original raw binary data payload that was signed.
        signature_b64: The companion digital signature, encoded as a Base64 
            UTF-8 string.

    Returns:
        True if the signature is authentic and verified successfully; False if 
        the signature is corrupt, the identity key is malformed, or verification
        fails.
    """

    try:
        pub_bytes = b64_to_bytes(sender_id_b64)
        signature = b64_to_bytes(signature_b64)
        public_key = ed25519.Ed25519PublicKey.from_public_bytes(pub_bytes)
        public_key.verify(signature, data)

        return True
    except (InvalidSignature, ValueError, Exception):
        return False