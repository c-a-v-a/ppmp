"""Error type definitions."""

from enum import IntEnum


class ErrorType(IntEnum):
    """Enumeration of error types used in protocol frames.

    Attributes:
        ERR_AUTH_FAILED: Authentication or signature verification failed.
        ERR_RATE_LIMIT: Request was rejected due to rate limiting.
    """

    ERR_AUTH_FAILED = 1
    ERR_RATE_LIMIT = 2