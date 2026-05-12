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
