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


class StreamIterator:
    """
    Iterator for streaming chat responses.
    Runs GLib main loop in a separate thread to receive D-Bus signals.
    """

    def __init__(self, bus, request_id: str, model: str, timeout: int = 60):
        """Initialize stream iterator."""
        if not DBUS_AVAILABLE:
            raise RuntimeError("D-Bus dependencies not available")

        self.bus = bus
        self.request_id = request_id
        self.model = model
        self.timeout = timeout

        self.chunk_queue: queue.Queue = queue.Queue()
        self.done = False
        self.error: Optional[Exception] = None

        self.mainloop: Optional[GLib.MainLoop] = None
        self.thread: Optional[threading.Thread] = None

        self._setup_signals()
