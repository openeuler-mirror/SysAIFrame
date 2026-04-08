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

    def _setup_signals(self):
        """Setup D-Bus signal handlers with request_id filtering"""
        try:
            match_rule = (
                f"type='signal',"
                f"interface='org.ctyunos.AIGateway.Chat',"
                f"member='StreamChunk',"
                f"arg0='{self.request_id}'"
            )
            self.bus.add_match_string(match_rule)

            match_rule_done = (
                f"type='signal',"
                f"interface='org.ctyunos.AIGateway.Chat',"
                f"member='StreamDone',"
                f"arg0='{self.request_id}'"
            )
            self.bus.add_match_string(match_rule_done)

            self.bus.add_signal_receiver(
                self._handle_chunk,
                signal_name="StreamChunk",
                dbus_interface="org.ctyunos.AIGateway.Chat",
                path="/org/ctyunos/AIGateway/Chat"
            )

            self.bus.add_signal_receiver(
                self._handle_done,
                signal_name="StreamDone",
                dbus_interface="org.ctyunos.AIGateway.Chat",
                path="/org/ctyunos/AIGateway/Chat"
            )

            logger.debug(f"Signal handlers setup for request_id: {self.request_id}")

        except Exception as e:
            logger.error(f"Failed to setup signal handlers: {e}")
            raise ServerError(f"Failed to setup streaming: {e}")

    def _handle_chunk(self, request_id: str, chunk: Dict[str, Any]):
        """Handle StreamChunk signal"""
        if request_id != self.request_id:
            return

        try:
            chunk_dict = self._dbus_to_python(chunk)
            chat_chunk = ChatChunk.from_dict(self.request_id, self.model, chunk_dict)
            self.chunk_queue.put(chat_chunk)
            logger.debug(f"Received chunk for {request_id}")
        except Exception as e:
            logger.error(f"Error processing chunk: {e}")
            self.error = ServerError(f"Error processing chunk: {e}")
            self.done = True
            if self.mainloop:
                self.mainloop.quit()
