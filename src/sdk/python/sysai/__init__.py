"""
SysAI SDK - Python client for SysAIFrame AI Gateway

Copyright (C) 2025 CTyunOS. All Rights Reserved.
"""

from .client import SysAIClient
from .types import (
    ChatMessage,
    ChatResponse,
    ChatChunk,
    Usage,
    SysAIConnectionError,
    ServiceUnavailableError,
    InvalidRequestError,
    SysAITimeoutError,
    ModelNotFoundError,
    ServerError,
)

__version__ = "0.1.0"
__all__ = [
    "SysAIClient",
    "ChatMessage",
    "ChatResponse",
    "ChatChunk",
    "Usage",
    "SysAIConnectionError",
    "ServiceUnavailableError",
    "InvalidRequestError",
    "SysAITimeoutError",
    "ModelNotFoundError",
    "ServerError",
]
