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


