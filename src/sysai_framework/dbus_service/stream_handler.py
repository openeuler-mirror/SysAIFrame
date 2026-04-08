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


