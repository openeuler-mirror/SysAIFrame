"""
Copyright (C) 2025 CTyunOS. All Rights Reserved.
File: service.py
Desc: D-Bus service implementation for SysAIFrame Gateway
Date: 2025-11-18
Author: Liu Mingran
"""

import os
import logging
import threading
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# Platform detection
try:
    import dbus
    import dbus.service
    from dbus.mainloop.glib import DBusGMainLoop
    from gi.repository import GLib
    DBUS_AVAILABLE = True
except ImportError:
    DBUS_AVAILABLE = False
    logger.warning("D-Bus dependencies not available - service will not start")


# Read interface XML
INTERFACE_XML_PATH = os.path.join(os.path.dirname(__file__), 'interface.xml')


class DBusAIGatewayService:
    """
    D-Bus service for SysAIFrame Gateway.
    Provides system-level interface for AI chat completions and admin operations.
    """

    BUS_NAME = 'org.ctyunos.AIGateway.Chat'
    OBJECT_PATH = '/org/ctyunos/AIGateway/Chat'
    ADMIN_OBJECT_PATH = '/org/ctyunos/AIGateway/Admin'
    INTERFACE_NAME = 'org.ctyunos.AIGateway.Chat'
    ADMIN_INTERFACE_NAME = 'org.ctyunos.AIGateway.Admin'

    def __init__(self, gateway_app=None, use_system_bus: bool = True):
        """
        Initialize D-Bus service.

        Args:
            gateway_app: FastAPI application instance (for accessing routes)
            use_system_bus: Use system bus (True) or session bus (False)
        """
        self.gateway_app = gateway_app
        self.use_system_bus = use_system_bus
        self.bus = None
        self.bus_name = None
        self.service_object = None
        self.admin_service_object = None
        self.mainloop = None
        self.thread = None
        self.running = False

        if not DBUS_AVAILABLE:
            logger.error("Cannot initialize D-Bus service: dependencies not available")
            return

        logger.info(f"D-Bus service initialized for {self.BUS_NAME}")

    def start(self):
        """Start D-Bus service in a separate thread."""
        if not DBUS_AVAILABLE:
            logger.warning("D-Bus not available, skipping service start")
            return

        if self.running:
            logger.warning("D-Bus service already running")
            return

        self.thread = threading.Thread(target=self._run_service, daemon=True)
        self.thread.start()
        logger.info("D-Bus service thread started")


