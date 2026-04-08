"""
Copyright (C) 2025 CTyunOS. All Rights Reserved.
File: admin_methods.py
Desc: D-Bus admin methods for model configuration management
Date: 2025-11-27
Author: Liu Mingran
"""

import logging
import json
from typing import Dict, Any, Tuple

logger = logging.getLogger(__name__)

# Platform detection
try:
    import dbus
    import dbus.service
    DBUS_AVAILABLE = True
except ImportError:
    DBUS_AVAILABLE = False
    dbus = None
    logger.warning("dbus-python not available")


# Base class depending on D-Bus availability
if DBUS_AVAILABLE:
    _BaseClass = dbus.service.Object
else:
    _BaseClass = object


def _dbus_method(interface, in_sig, out_sig):
    """Decorator factory that wraps dbus.service.method or returns identity"""
    if DBUS_AVAILABLE:
        return dbus.service.method(interface, in_signature=in_sig, out_signature=out_sig)
    else:
        def identity(func):
            return func
        return identity


class AdminServiceObject(_BaseClass):
    """
    D-Bus service object implementing model configuration admin methods.
    """

    INTERFACE_NAME = 'org.ctyunos.AIGateway.Admin'

    def __init__(self, bus_name, object_path):
        """
        Initialize admin service object.

        Args:
            bus_name: D-Bus bus name
            object_path: D-Bus object path
        """
        if DBUS_AVAILABLE:
            super().__init__(bus_name, object_path)

        # Import config manager
        try:
            from sysai_framework.config import get_config_manager
            self.config_manager = get_config_manager()
            logger.info("Admin service object initialized with config manager")
        except Exception as e:
            logger.error(f"Failed to initialize config manager: {e}", exc_info=True)
            self.config_manager = None


