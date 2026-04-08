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
