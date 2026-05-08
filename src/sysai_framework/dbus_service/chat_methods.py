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


class ChatServiceObject(dbus.service.Object if DBUS_AVAILABLE else object):
    """
    D-Bus service object implementing chat completion methods.
    """

    INTERFACE_NAME = 'org.ctyunos.AIGateway.Chat'

    def __init__(self, bus_name, object_path, gateway_app=None):
        """
        Initialize chat service object.

        Args:
            bus_name: D-Bus bus name
            object_path: D-Bus object path
            gateway_app: FastAPI application instance
        """
        if DBUS_AVAILABLE:
            super().__init__(bus_name, object_path)

        self.gateway_app = gateway_app
        self.stream_handler = StreamHandler(self)

        # Import dependencies
        try:
            from sysai_framework.config import get_config_manager
            from sysai_framework.router.model_router import ModelRouter

            self.config_manager = get_config_manager()
            self.model_router = ModelRouter(self.config_manager)

            logger.info("Chat service object initialized with dependencies")
        except Exception as e:
            logger.error(f"Failed to initialize dependencies: {e}", exc_info=True)
            self.config_manager = None
            self.model_router = None


