"""
Copyright (C) 2025 CTyunOS. All Rights Reserved.
File: cli/ai_config.py
Desc: Configuration management CLI tool - main entry point
Date: 2025-10-22
Author: Liu Mingran
"""

import click
import yaml
import os
import sys
from pathlib import Path

from .commands.model import model
from .commands.routing import routing
from .commands.service import service
from .utils.output import Output
from .utils.dbus_client import (
    get_dbus_client,
    ServiceNotRunningError,
    DBusNotAvailableError,
    DBusClientError,
)


# Default configuration path
from .constants import DEFAULT_CONFIG_PATH
