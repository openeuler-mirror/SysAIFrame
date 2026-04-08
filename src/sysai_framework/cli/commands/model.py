"""
Copyright (C) 2025 CTyunOS. All Rights Reserved.
File: cli/commands/model.py
Desc: Model management CLI commands
Date: 2025-11-27
Author: Liu Mingran
"""

import os
import sys
import click
from typing import Optional

from ..validators.model_validator import ModelValidator
from ..utils.output import Output
from ..utils.mode_switch import auto_execute
from ..utils.dbus_client import (
    get_dbus_client,
    ServiceNotRunningError,
    DBusNotAvailableError,
    DBusClientError,
)


# Default configuration path
from ..constants import DEFAULT_CONFIG_PATH


def _parse_bool_option(value: str) -> bool:
    """
    Parse a string value to bool (case-insensitive).

    Supports 'true'/'True'/'TRUE' as True and 'false'/'False'/'FALSE' as False.

    Args:
        value: String value to parse

    Returns:
        bool: Parsed boolean value

    Raises:
        click.BadParameter: If value is not a valid boolean string
    """
    if not isinstance(value, str):
        raise click.BadParameter(f"Expected string, got {type(value).__name__}")

    value_lower = value.lower()
    if value_lower == 'true':
        return True
    elif value_lower == 'false':
        return False
    else:
        raise click.BadParameter(
            f"Invalid boolean value '{value}'. Expected 'true' or 'false' (case-insensitive)"
        )


def _validate_priority(ctx, param, value):
    """
    Validate priority parameter.

    Args:
        ctx: Click context
        param: Parameter being validated
        value: Value to validate

    Returns:
        Validated value

    Raises:
        click.BadParameter: If value is not a valid priority
    """
    if value is None:
        return None

    try:
        priority = int(value)
        if priority < 1 or priority > 100:
            raise click.BadParameter("Priority must be between 1 and 100")
        return priority
    except ValueError:
        raise click.BadParameter(f"Invalid priority value: {value}. Must be an integer.")


def _validate_timeout(ctx, param, value):
    """
    Validate timeout parameter.

    Args:
        ctx: Click context
        param: Parameter being validated
        value: Value to validate

    Returns:
        Validated value

    Raises:
        click.BadParameter: If value is not a valid timeout
    """
    if value is None:
        return None

    try:
        timeout = int(value)
        if timeout < 1 or timeout > 3600:
            raise click.BadParameter("Timeout must be between 1 and 3600 seconds")
        return timeout
    except ValueError:
        raise click.BadParameter(f"Invalid timeout value: {value}. Must be an integer.")


def _validate_max_retries(ctx, param, value):
    """
    Validate max_retries parameter.

    Args:
        ctx: Click context
        param: Parameter being validated
        value: Value to validate

    Returns:
        int: Validated max_retries value

    Raises:
        click.BadParameter: If value out of valid range
    """
    if value < 0:
        raise click.BadParameter('Max retries must be >= 0')
    if value > 10:
        raise click.BadParameter('Max retries must be <= 10')
    return value


@click.group()
def model():
    """Model management commands"""
    pass


def _add_model_via_dbus(normalized_data: dict, force: bool, set_as_default: bool = False) -> 'OperationResult':
    """
    Add model via D-Bus (service must be running).

    Returns:
        OperationResult with status and data
    """
    client = get_dbus_client()
    return client.add_model(normalized_data, force=force, set_as_default=set_as_default)


def _add_model_offline(normalized_data: dict, force: bool, config_path: str, set_as_default: bool = False) -> 'OperationResult':
    """
    Add model directly to config file (offline mode).

    Returns:
        OperationResult with status and data
    """
    from sysai_framework.config import ModelConfigManager
    from sysai_framework.core.status_codes import (
        OperationResult, CONFIG_NOT_FOUND, CONFIG_PERMISSION_DENIED
    )

    if not os.path.exists(config_path):
        return OperationResult.error_result(
            CONFIG_NOT_FOUND,
            details={"path": config_path}
        )

    if not os.access(config_path, os.W_OK):
        return OperationResult.error_result(
            CONFIG_PERMISSION_DENIED,
            details={"path": config_path}
        )

    manager = ModelConfigManager(config_path=config_path, allow_create_default=False)
    return manager.add_model(
        normalized_data,
        persist=True,
        force=force,
        set_as_default=set_as_default
    )
