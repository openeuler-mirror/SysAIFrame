"""
Copyright (C) 2025 CTyunOS. All Rights Reserved.
File: stream_handler.py
Desc: Stream handling for D-Bus chat completion streaming
Date: 2025-11-18
Author: Liu Mingran
"""

import logging
import threading
import time
import json
import asyncio
from typing import Dict, Any, Generator

logger = logging.getLogger(__name__)


class StreamHandler:
    """
    Handles streaming responses for D-Bus chat completion streaming.
    Manages background threads for stream processing and signal emission.
    """

    def __init__(self, service_object):
        """
        Initialize stream handler.

        Args:
            service_object: ChatServiceObject instance for signal emission
        """
        self.service_object = service_object
        self.active_streams = {}  # request_id -> thread

    def start_stream(self, request_id: str, request: Dict):
        """
        Start processing a streaming request in background.

        Args:
            request_id: Unique request identifier
            request: Request parameters
        """
        if request_id in self.active_streams:
            logger.warning(f"Stream {request_id} already active")
            return

        # Start streaming in a background thread
        thread = threading.Thread(
            target=self._process_stream,
            args=(request_id, request),
            daemon=True
        )
        self.active_streams[request_id] = thread
        thread.start()

        logger.info(f"Started stream processing for {request_id}")


