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
    from .dbus_client import get_dbus_client, ServiceNotRunningError, DBusNotAvailableError
    from .output import Output
    from ..ai_config import DEFAULT_CONFIG_PATH

    try:
        # Try to execute via D-Bus (online mode)
        client = get_dbus_client()
        if client.is_service_running():
            # Service is running, check if config path matches
            try:
                service_config_path = client.get_service_config_path()

                # Normalize paths (resolve to absolute paths, handle symlinks)
                if config_path:
                    user_path = os.path.realpath(os.path.abspath(config_path))
                else:
                    # User didn't specify path, use default path
                    user_path = os.path.realpath(os.path.abspath(DEFAULT_CONFIG_PATH))

                # Normalize service path, but treat empty string as None
                if service_config_path and service_config_path.strip():
                    service_path = os.path.realpath(os.path.abspath(service_config_path))
                else:
                    service_path = None

                # Compare paths
                if service_path and user_path != service_path:
                    # Path mismatch, use offline mode
                    logger.info(f"Config path mismatch: user={user_path}, service={service_path}")
                    if not silent_offline:
                        Output.info(f"Specified config path differs from service config, using offline mode")

                    # Check if file exists
                    if require_config_file and not os.path.exists(user_path):
                        Output.error(f"Configuration file not found: {user_path}")
                        sys.exit(Output.EXIT_CONFIG_NOT_FOUND)

                    return offline_func()
                else:
                    # Path matches or service path unavailable, use online mode (via D-Bus)
                    logger.debug(f"Config path matches service config, using online mode: {user_path}")
                    return online_func(client)
            except Exception as e:
                # If we can't get service config path, fall back to online mode
                logger.warning(f"Failed to get service config path: {e}, using online mode")
                return online_func(client)
        else:
            # Service not running, automatically switch to offline mode
            # Determine the config path to use
            if config_path:
                user_path = os.path.realpath(os.path.abspath(config_path))
            else:
                user_path = os.path.realpath(os.path.abspath(DEFAULT_CONFIG_PATH))

            logger.info(f"Service not running, switching to offline mode for '{operation_name}'")
            if not silent_offline:
                Output.info(f"Service is not running, switching to offline mode")

            # Check if config file exists (if required)
            if require_config_file:
                if not os.path.exists(user_path):
                    Output.error(f"Configuration file not found: {user_path}")
                    Output.info("The service must be running to create initial configuration.")
                    Output.info("Please start the service first: sudo systemctl start sysaiframe")
                    sys.exit(Output.EXIT_CONFIG_NOT_FOUND)

            if not silent_offline:
                Output.info(f"Executing '{operation_name}' in offline mode")
            result = offline_func()
            if not silent_offline:
                Output.warning("Changes saved to config file. Restart service to apply: sudo systemctl restart sysaiframe")
            return result

    except ServiceNotRunningError:
        # Service not running, use offline mode
        # Determine the config path to use
        if config_path:
            user_path = os.path.realpath(os.path.abspath(config_path))
        else:
            user_path = os.path.realpath(os.path.abspath(DEFAULT_CONFIG_PATH))

        logger.info(f"Service not running, switching to offline mode for '{operation_name}'")
        if not silent_offline:
            Output.info(f"Service is not running, switching to offline mode")

        # Check if config file exists (if required)
        if require_config_file:
            if not os.path.exists(user_path):
                Output.error(f"Configuration file not found: {user_path}")
                Output.info("The service must be running to create initial configuration.")
                Output.info("Please start the service first: sudo systemctl start sysaiframe")
                sys.exit(Output.EXIT_CONFIG_NOT_FOUND)

        if not silent_offline:
            Output.info(f"Executing '{operation_name}' in offline mode")
        result = offline_func()
        if not silent_offline:
            Output.warning("Changes saved to config file. Restart service to apply: sudo systemctl restart sysaiframe")
        return result

    except DBusNotAvailableError:
        # D-Bus not available, use offline mode
        # Determine the config path to use
        if config_path:
            user_path = os.path.realpath(os.path.abspath(config_path))
        else:
            user_path = os.path.realpath(os.path.abspath(DEFAULT_CONFIG_PATH))

        logger.warning("D-Bus not available, using offline mode")
        if not silent_offline:
            Output.warning("D-Bus not available, using offline mode")

        # Check if config file exists (if required)
        if require_config_file:
            if not os.path.exists(user_path):
                Output.error(f"Configuration file not found: {user_path}")
                Output.info("Cannot operate without configuration file when D-Bus is unavailable.")
                sys.exit(Output.EXIT_CONFIG_NOT_FOUND)

        if not silent_offline:
            Output.info(f"Executing '{operation_name}' in offline mode")
        result = offline_func()
        if not silent_offline:
            Output.warning("Changes saved to config file. Restart service to apply: sudo systemctl restart sysaiframe")
        return result
