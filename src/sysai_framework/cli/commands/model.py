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
