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


