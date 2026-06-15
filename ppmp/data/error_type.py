"""Error type definitions."""

from enum import StrEnum


class ErrorType(StrEnum):
    """Enumeration of error types used in protocol frames.

    Attributes:
        ERR_AUTH_FAILED: Authentication or signature verification failed.
        ERR_RATE_LIMIT: Request was rejected due to rate limiting.
    """

    ERR_AUTH_FAILED = "ERR_AUTH_FAILED"
    ERR_RATE_LIMIT = "ERR_RATE_LIMIT"