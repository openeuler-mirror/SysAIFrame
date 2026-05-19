"""
Streaming support for SysAI SDK

Copyright (C) 2025 CTyunOS. All Rights Reserved.
"""

import logging
import threading
import queue
from typing import Iterator, Optional, Dict, Any

logger = logging.getLogger(__name__)

try:
    import dbus
    from gi.repository import GLib
    DBUS_AVAILABLE = True
except ImportError:
    DBUS_AVAILABLE = False
    logger.warning("D-Bus dependencies not available")

from .types import ChatChunk, ServerError, SysAITimeoutError
