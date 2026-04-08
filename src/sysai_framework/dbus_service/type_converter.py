"""
Copyright (C) 2025 CTyunOS. All Rights Reserved.
File: type_converter.py
Desc: Type conversion utilities between Python and D-Bus types
Date: 2025-11-18
Author: Liu Mingran
"""

import logging
from typing import Any, Dict, List, Union

logger = logging.getLogger(__name__)

# Platform detection for conditional imports
try:
    import dbus
    DBUS_AVAILABLE = True
except ImportError:
    DBUS_AVAILABLE = False
    logger.warning("dbus-python not available - D-Bus service will not work on this platform")


