"""Error frame definitions."""

from dataclasses import dataclass

from error_type import ErrorType
from frame import Frame


@dataclass
class ErrorFrame(Frame):
    """Frame used to report protocol errors.

    Attributes:
        code: Machine-readable error code identifying the type of error.
        message: Human-readable description of the error.
    """

    code: ErrorType
    message: str