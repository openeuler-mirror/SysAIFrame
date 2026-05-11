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


@click.group()
@click.version_option(version='1.0.0', prog_name='ai-config')
def cli():
    """
    SysAIFrame configuration management tool

    Manage AI model configurations, routing settings, and more.

    \b
    Examples:
      ai-config model add mymodel --api https://api.example.com/v1 --api_key sk-xxx
      ai-config model list
      ai-config show
      ai-config validate
    """
    pass


# Register sub-command groups
cli.add_command(model)
cli.add_command(routing)
cli.add_command(service)
