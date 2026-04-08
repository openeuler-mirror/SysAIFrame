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


@model.command()
@click.option('--name', required=True, help='Model name (required)')
@click.option('--api', required=True, help='API base URL (required)')
@click.option('--api_key', default=None, help='API key (required for cloud providers)')
@click.option('--provider', default='openai_like',
              help='Provider type: openai, deepseek, dashscope, moonshot, ollama, openai_like')
@click.option('--instance_id', default=None, help='Instance ID (auto-generated if not provided)')
@click.option('--priority', default=1, type=int, callback=_validate_priority,
              help='Model priority (default: 1, range: 1-100)')
@click.option('--capabilities', default='general',
              help='Comma-separated capabilities, e.g., general,code,analysis (default: general)')
@click.option('--timeout', default=30, type=int, callback=_validate_timeout,
              help='Request timeout in seconds (default: 30, range: 1-3600)')
@click.option('--max_retries', default=3, type=int, callback=_validate_max_retries,
              help='Max retry attempts (default: 3, range: 0-10)')
@click.option('--streaming', default='true', type=_parse_bool_option,
              help='Enable streaming support: true/false (default: true, case-insensitive)')
@click.option('--config_path', default=DEFAULT_CONFIG_PATH,
              help=f'Configuration file path (default: {DEFAULT_CONFIG_PATH})')
@click.option('--dry_run', is_flag=True, help='Validate only, do not add model')
@click.option('--force', is_flag=True, help='Force overwrite if instance_id exists')
@click.option('--default', 'set_as_default', is_flag=True,
              help='Set this model as the default model')
def add(
    name: str,
    api: str,
    api_key: Optional[str],
    provider: str,
    instance_id: Optional[str],
    priority: int,
    capabilities: str,
    timeout: int,
    max_retries: int,
    streaming: bool,
    config_path: str,
    dry_run: bool,
    force: bool,
    set_as_default: bool
):
    """
    Add a new model configuration

    Examples:
      ai-config model add --name mymodel --api https://api.example.com/v1 --api_key sk-xxx
      ai-config model add --name deepseek --api https://api.deepseek.com/v1 --provider deepseek --api_key sk-xxx
    """
    # Build model data dict from CLI options
    model_data = {
        'name': name,
        'api_base': api,
        'api_key': api_key,
        'provider': provider,
        'instance_id': instance_id,
        'priority': priority,
        'capabilities': capabilities,
        'timeout': timeout,
        'max_retries': max_retries,
        'supports_streaming': streaming,
    }

    # Use ModelValidator to validate and normalize
    validator = ModelValidator()
    is_valid, errors, warnings = validator.validate(model_data)

    # Print warnings
    for warning in warnings:
        Output.warning(warning)

    # Print validation errors if any
    if not is_valid:
        Output.validation_errors(errors)
        sys.exit(Output.EXIT_VALIDATION_ERROR)

    # Dry run mode - just validate
    if dry_run:
        Output.success("Validation passed. Model data is valid.")
        return

    # Normalize data for saving
    normalized_data = ModelValidator.normalize_model_data(model_data)

    # Execute with auto mode switch
    result = auto_execute(
        online_func=lambda client: _add_model_via_dbus(normalized_data, force, set_as_default),
        offline_func=lambda: _add_model_offline(normalized_data, force, config_path, set_as_default),
        operation_name="add model",
        config_path=config_path
    )

    # Handle result
    if result.success:
        Output.success(result.get_message())
        sys.exit(Output.EXIT_SUCCESS)
    else:
        Output.error(result.get_message())
        sys.exit(Output.EXIT_WRITE_FAILED)
