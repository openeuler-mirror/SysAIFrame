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


@cli.command()
@click.option('--config_path', default=DEFAULT_CONFIG_PATH,
              help=f'Path to configuration file (default: {DEFAULT_CONFIG_PATH})')
@click.option('--json', 'as_json', is_flag=True, help='Output as JSON')
def show(config_path: str, as_json: bool):
    """Show current configuration"""
    if not os.path.exists(config_path):
        Output.error(f"Configuration file not found: {config_path}")
        sys.exit(Output.EXIT_CONFIG_NOT_FOUND)

    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)

        # Sanitize sensitive information before output
        sanitized_config = Output.sanitize_sensitive_data(config)

        if as_json:
            import json
            click.echo(json.dumps(sanitized_config, indent=2, ensure_ascii=False))
        else:
            click.echo(yaml.dump(sanitized_config, default_flow_style=False, allow_unicode=True))

    except yaml.YAMLError as e:
        Output.error(f"Invalid YAML: {e}")
        sys.exit(Output.EXIT_VALIDATION_ERROR)
    except Exception as e:
        Output.error(f"Failed to read configuration: {e}")
        sys.exit(Output.EXIT_CONFIG_NOT_FOUND)
