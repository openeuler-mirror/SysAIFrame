"""
Copyright (C) 2025 CTyunOS. All Rights Reserved.
File: cli/utils/dbus_client.py
Desc: D-Bus client for CLI to communicate with SysAIFrame service
Date: 2025-11-27
Author: Liu Mingran
"""

import json
import logging
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger(__name__)

# D-Bus service constants
BUS_NAME = 'org.ctyunos.AIGateway.Chat'
ADMIN_OBJECT_PATH = '/org/ctyunos/AIGateway/Admin'
ADMIN_INTERFACE = 'org.ctyunos.AIGateway.Admin'

# Platform detection
try:
    import dbus
    DBUS_AVAILABLE = True
except ImportError:
    DBUS_AVAILABLE = False
    logger.debug("dbus-python not available")


class DBusClientError(Exception):
    """Base exception for D-Bus client errors"""
    pass


class ServiceNotRunningError(DBusClientError):
    """Raised when the SysAIFrame service is not running"""
    pass


class DBusNotAvailableError(DBusClientError):
    """Raised when D-Bus is not available on the system"""
    pass


class AdminDBusClient:
    """
    D-Bus client for model configuration admin operations.

    Usage:
        client = AdminDBusClient()
        if client.is_service_running():
            success, message, instance_id = client.add_model(model_data)
    """

    def __init__(self, use_system_bus: bool = True):
        """
        Initialize D-Bus client.

        Args:
            use_system_bus: Use system bus (True) or session bus (False)
        """
        self.use_system_bus = use_system_bus
        self._bus = None
        self._admin_interface = None
