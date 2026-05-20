"""
SysAI Client - Main client for interacting with SysAIFrame

Copyright (C) 2025 CTyunOS. All Rights Reserved.
"""

import logging
from typing import List, Optional, Dict, Any, Union, Iterator

logger = logging.getLogger(__name__)

try:
    import dbus
    from dbus.mainloop.glib import DBusGMainLoop
    DBUS_AVAILABLE = True
except ImportError:
    DBUS_AVAILABLE = False
    logger.warning("D-Bus dependencies not available")

from .types import (
    ChatMessage,
    ChatResponse,
    ChatChunk,
    SysAIConnectionError,
    ServiceUnavailableError,
    InvalidRequestError,
    ServerError,
    ModelNotFoundError,
    SysAITimeoutError,
)
from .streaming import StreamIterator


class SysAIClient:
    """
    Client for SysAIFrame AI Gateway.

    Provides methods for chat completion (streaming and non-streaming),
    model listing, and service status.
    """

    BUS_NAME = "org.ctyunos.AIGateway.Chat"
    OBJECT_PATH = "/org/ctyunos/AIGateway/Chat"
    INTERFACE_NAME = "org.ctyunos.AIGateway.Chat"
