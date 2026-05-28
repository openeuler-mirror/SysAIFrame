"""
Copyright (C) 2025 CTyunOS. All Rights Reserved.
File: cli/commands/gateway.py
Desc: CLI commands for gateway configuration (remote access and port settings)
Date: 2025-05-12
Author: Liu Mingran
"""

import click
import sys
import logging
from typing import Optional

from ..utils.output import Output
from ..utils.mode_switch import auto_execute
from ..constants import DEFAULT_CONFIG_PATH

logger = logging.getLogger(__name__)


@click.group(name='gateway')
def gateway():
    """Gateway configuration management commands"""
    pass


@gateway.command('show')
@click.option('--json', 'json_output', is_flag=True,
              help='Output in JSON format')
@click.option('--config_path', 'config_file',
              help=f'Configuration file path (default: {DEFAULT_CONFIG_PATH})')
def gateway_show(json_output: bool, config_file: Optional[str]):
    """Display gateway configuration (remote access and port settings)"""
    from sysai_framework.config.model_config import ModelConfigManager
    from sysai_framework.cli.constants import DEFAULT_CONFIG_PATH

    if not config_file:
        config_file = DEFAULT_CONFIG_PATH

    def online_mode(client):
        try:
            gateway_config = client.get_gateway_config()

            if json_output:
                Output.print_json(gateway_config)
                return 0

            remote_access = gateway_config.get('remote_access', False)
            port = gateway_config.get('port', 6000)
            effective_host = '0.0.0.0' if remote_access else '127.0.0.1'

            Output.section("Gateway Configuration")
            Output.info(f"  Remote access: {'enabled (0.0.0.0)' if remote_access else 'disabled (127.0.0.1)'}")
            Output.info(f"  Port: {port}")
            Output.info(f"  Effective binding: {effective_host}:{port}")

            return 0

        except Exception as e:
            Output.error(f"Failed to get gateway config: {e}")
            return 1

    def offline_mode():
        try:
            config_manager = ModelConfigManager(config_path=config_file, allow_create_default=False)
            gateway_config = config_manager.get_gateway_config()
            remote_access = gateway_config.get('remote_access', False)
            port = gateway_config.get('port', 6000)
            effective_host = '0.0.0.0' if remote_access else '127.0.0.1'

            if json_output:
                Output.print_json({
                    "remote_access": remote_access,
                    "port": port,
                    "effective_host": effective_host
                })
                return 0

            Output.section("Gateway Configuration")
            Output.info(f"  Remote access: {'enabled (0.0.0.0)' if remote_access else 'disabled (127.0.0.1)'}")
            Output.info(f"  Port: {port}")
            Output.info(f"  Effective binding: {effective_host}:{port}")

            return 0

        except Exception as e:
            Output.error(f"Failed to get gateway config: {e}")
            return 1

    return auto_execute(
        online_func=online_mode,
        offline_func=offline_mode,
        operation_name="gateway show",
        config_path=config_file,
        silent_offline=False
    )


@gateway.command('set-remote-access')
@click.argument('enabled', type=click.BOOL)
@click.option('--config_path', 'config_file',
              help=f'Configuration file path (default: {DEFAULT_CONFIG_PATH})')
def set_remote_access(enabled: bool, config_file: Optional[str]):
    """Set remote access switch (true = allow cross-node, false = local only)

    Changing this requires service restart: sudo systemctl restart sysaiframe

    Examples:
        ai-config gateway set-remote-access true
        ai-config gateway set-remote-access false
    """
    from sysai_framework.config.model_config import ModelConfigManager
    from sysai_framework.cli.constants import DEFAULT_CONFIG_PATH

    if not config_file:
        config_file = DEFAULT_CONFIG_PATH

    def online_mode(client):
        try:
            success, message = client.set_remote_access(enabled)
            if success:
                Output.success(f"Remote access set to: {'enabled (0.0.0.0)' if enabled else 'disabled (127.0.0.1)'}")
                Output.warning("This change requires service restart to take effect: sudo systemctl restart sysaiframe")
                return 0
            else:
                Output.error(f"Failed to set remote access via D-Bus: {message}")
                return 1
        except Exception as e:
            Output.error(f"Failed to set remote access: {e}")
            return 1

    def offline_mode():
        try:
            config_manager = ModelConfigManager(config_path=config_file, allow_create_default=False)
            result = config_manager.update_gateway_config(
                {'remote_access': enabled},
                persist=True,
                require_file_lock=True
            )
            if result:
                Output.success(f"Remote access set to: {'enabled (0.0.0.0)' if enabled else 'disabled (127.0.0.1)'}")
                Output.warning("This change requires service restart to take effect: sudo systemctl restart sysaiframe")
                return 0
            else:
                Output.error("Failed to update gateway config")
                return 1
        except Exception as e:
            Output.error(f"Failed to set remote access: {e}")
            return 1

    return sys.exit(auto_execute(
        online_func=online_mode,
        offline_func=offline_mode,
        operation_name="gateway set-remote-access",
        config_path=config_file,
        silent_offline=False
    ))


@gateway.command('set-port')
@click.argument('port', type=click.INT)
@click.option('--config_path', 'config_file',
              help=f'Configuration file path (default: {DEFAULT_CONFIG_PATH})')
def set_port(port: int, config_file: Optional[str]):
    """Set API server port (1-65535)

    Changing this requires service restart: sudo systemctl restart sysaiframe

    Examples:
        ai-config gateway set-port 6000
        ai-config gateway set-port 8080
    """
    if port < 1 or port > 65535:
        Output.error(f"Port must be between 1 and 65535, got {port}")
        sys.exit(Output.EXIT_VALIDATION_ERROR)

    from sysai_framework.config.model_config import ModelConfigManager
    from sysai_framework.cli.constants import DEFAULT_CONFIG_PATH

    if not config_file:
        config_file = DEFAULT_CONFIG_PATH

    def online_mode(client):
        try:
            success, message = client.set_gateway_port(port)
            if success:
                Output.success(f"Gateway port set to: {port}")
                Output.warning("This change requires service restart to take effect: sudo systemctl restart sysaiframe")
                return 0
            else:
                Output.error(f"Failed to set gateway port via D-Bus: {message}")
                return 1
        except Exception as e:
            Output.error(f"Failed to set gateway port: {e}")
            return 1

    def offline_mode():
        try:
            config_manager = ModelConfigManager(config_path=config_file, allow_create_default=False)
            result = config_manager.update_gateway_config(
                {'port': port},
                persist=True,
                require_file_lock=True
            )
            if result:
                Output.success(f"Gateway port set to: {port}")
                Output.warning("This change requires service restart to take effect: sudo systemctl restart sysaiframe")
                return 0
            else:
                Output.error("Failed to update gateway config")
                return 1
        except Exception as e:
            Output.error(f"Failed to set gateway port: {e}")
            return 1

    return sys.exit(auto_execute(
        online_func=online_mode,
        offline_func=offline_mode,
        operation_name="gateway set-port",
        config_path=config_file,
        silent_offline=False
    ))