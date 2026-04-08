"""
Copyright (C) 2025 CTyunOS. All Rights Reserved.
File: cli/utils/mode_switch.py
Desc: Automatic mode switching utility for CLI commands
     Automatically switches between online (D-Bus) and offline (direct file) modes
Date: 2025-11-27
Author: Liu Mingran
"""

import os
import sys
import logging
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


def auto_execute(
    online_func: Callable,
    offline_func: Callable,
    operation_name: str = "operation",
    require_config_file: bool = True,
    config_path: Optional[str] = None,
    silent_offline: bool = False
) -> Any:
    """
    Automatically detect service status and select execution mode

    If service is running: Call via D-Bus (online mode), changes take effect immediately
    If service is not running: Directly modify config file (offline mode), changes take effect on next startup

    Args:
        online_func: Function to call when service is running (D-Bus), takes (client) as parameter
        offline_func: Function to call when service is not running (direct file operation), takes no parameters
        operation_name: Operation name (for logging and error messages)
        require_config_file: Whether config file is required in offline mode
        config_path: Config file path (for offline mode check)
        silent_offline: If True, don't print informational messages in offline mode (for read-only operations)

    Returns:
        Function execution result
    """
