"""Module for managing Diffie-Hellman key exchanges using X25519 and HKDF."""

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import x25519
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from .utils import b64_to_bytes, bytes_to_b64


def generate_dh_keypair() -> x25519.X25519PrivateKey:
    """Generates a new, random X25519 private key for Diffie-Hellman key exchange.

    Returns:
        An instance of X25519PrivateKey to be used for shared secret derivation.
    """
    return x25519.X25519PrivateKey.generate()


def get_dh_pubkey_b64(private_key: x25519.X25519PrivateKey) -> str:
    """Extracts the public key from an X25519 private key as a Base64 string.

    Args:
        private_key: The X25519PrivateKey instance to derive the public key from.

    Returns:
        The raw public key bytes formatted into a Base64 UTF-8 string.
    """

    pub_bytes = private_key.public_key().public_bytes_raw()
    return bytes_to_b64(pub_bytes)


def generate_session_key(
    private_key: x25519.X25519PrivateKey, peer_dh_pubkey_b64: str
) -> bytes:
    """Performs an X25519 exchange and runs HKDF to derive a symmetric session key.

    Args:
        private_key: The local peer's ephemeral X25519PrivateKey instance.
        peer_dh_pubkey_b64: The remote peer's public key, encoded as a Base64
            UTF-8 string.

    Returns:
        A 32-byte cryptographically secure symmetric key suitable for AES or
        ChaCha20 encryption.

    Raises:
        ValueError: If the remote peer's public key is malformed or invalid
            for X25519 operations.
    """

    peer_pub_bytes = b64_to_bytes(peer_dh_pubkey_b64)
    peer_public_key = x25519.X25519PublicKey.from_public_bytes(peer_pub_bytes)

    # Compute raw Diffie-Hellman shared secret
    shared_secret = private_key.exchange(peer_public_key)

    # Derive high-entropy symmetric key from shared secret using HKDF
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=None,
        info=b"P2P-MSG-PROTOCOL-V1",
    )
    return hkdf.derive(shared_secret)