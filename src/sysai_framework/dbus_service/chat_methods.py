"""
Copyright (C) 2025 CTyunOS. All Rights Reserved.
File: chat_methods.py
Desc: D-Bus chat completion method implementation
Date: 2025-11-18
Author: Liu Mingran
"""

import logging
import json
import time
import uuid
from typing import Dict, Any

logger = logging.getLogger(__name__)

# Platform detection
try:
    import dbus
    import dbus.service
    DBUS_AVAILABLE = True
except ImportError:
    DBUS_AVAILABLE = False
    logger.warning("dbus-python not available")

from .type_converter import request_to_python, response_to_dbus
from .stream_handler import StreamHandler


