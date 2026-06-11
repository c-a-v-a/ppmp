"""Hello frame definitions."""

from dataclasses import dataclass

from frame import Frame

@dataclass
class HelloFrame(Frame):
    """Frame for session initialization and key exchange.

    Attributes:
        sender_id: Unique identifier of the sender.
        dh_pubkey: Sender's Diffie-Hellman public key used for key exchange.
        sig: Digital signature used to authenticate the frame contents.
    """
    sender_id: str
    dh_pubkey: str
    sig: str