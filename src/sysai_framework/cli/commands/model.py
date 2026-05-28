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
        int: Validated priority value
        
    Raises:
        click.BadParameter: If value is out of valid range
    """
    if value < 1:
        raise click.BadParameter('Priority must be >= 1')
    if value > 100:
        raise click.BadParameter('Priority must be <= 100')
    return value


def _validate_timeout(ctx, param, value):
    """
    Validate timeout parameter.

    Args:
        ctx: Click context
        param: Parameter being validated
        value: Value to validate

    Returns:
        int or None: Validated timeout value, None means inherit from routing

    Raises:
        click.BadParameter: If value is out of valid range
    """
    if value is None:
        return None  # inherit from routing timeout
    if value < 3:
        raise click.BadParameter('Timeout must be >= 3 seconds')
    if value > 3600:
        raise click.BadParameter('Timeout must be <= 3600 seconds (1 hour)')
    return value


def _validate_stream_timeout(ctx, param, value):
    """
    Validate stream_timeout parameter.

    Args:
        ctx: Click context
        param: Parameter being validated
        value: Value to validate

    Returns:
        int or None: Validated stream_timeout value, None means inherit from timeout

    Raises:
        click.BadParameter: If value is out of valid range
    """
    if value is None:
        return None  # inherit from timeout
    if value < 3:
        raise click.BadParameter('Stream timeout must be >= 3 seconds')
    if value > 3600:
        raise click.BadParameter('Stream timeout must be <= 3600 seconds (1 hour)')
    return value


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
        click.BadParameter: If value is out of valid range
    """
    if value < 0:
        raise click.BadParameter('Max retries must be >= 0')
    if value > 10:
        raise click.BadParameter('Max retries must be <= 10')
    return value


@click.group()
def model():
    """Model configuration management commands"""
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
    
    # Check config file exists
    if not os.path.exists(config_path):
        return OperationResult.error_result(
            CONFIG_NOT_FOUND,
            details={"path": config_path}
        )
    
    # Check write permission
    if not os.access(config_path, os.W_OK):
        return OperationResult.error_result(
            CONFIG_PERMISSION_DENIED,
            details={"path": config_path}
        )
    
    # Use ModelConfigManager to add model (now returns OperationResult)
    # In CLI offline mode, don't allow creating default config to avoid reading default configs
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
              help='Provider type: openai, deepseek, dashscope, moonshot, ollama, openai_like, volcengine, zai, minimax, azure')
@click.option('--instance_id', default=None, help='Instance ID (auto-generated if not provided)')
@click.option('--priority', default=1, type=int, callback=_validate_priority,
              help='Model priority (default: 1, range: 1-100)')
@click.option('--capabilities', default='general', 
              help='Comma-separated capabilities, e.g., general,code,analysis (default: general)')
@click.option('--timeout', default=None, type=int, callback=_validate_timeout,
              help='Request timeout in seconds (range: 3-3600). None means inherit from routing timeout')
@click.option('--stream_timeout', default=None, type=int, callback=_validate_stream_timeout,
              help='Streaming inter-chunk timeout in seconds (range: 3-3600). None means inherit from timeout')
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
    stream_timeout: int,
    max_retries: int,
    streaming: bool,
    config_path: str,
    dry_run: bool,
    force: bool,
    set_as_default: bool
):
    """
    Add a new model configuration
    
    This command automatically detects service status:
    - If service is running: Connects via D-Bus, changes take effect immediately
    - If service is not running: Automatically switches to offline mode, modifies config file directly
    
    Examples:
    
    \b
      # Add a DeepSeek model (service running - takes effect immediately)
      ai-config model add \\
        --name deepseek-chat \\
        --api https://api.deepseek.com/v1 \\
        --api_key sk-your-key \\
        --provider deepseek
    
    \b
      # Add a local Ollama model (no API key needed)
      ai-config model add \\
        --name llama2 \\
        --api http://localhost:11434 \\
        --provider ollama
    
    \b
      # Add a model with multiple capabilities
      ai-config model add \\
        --name gpt-4 \\
        --api https://api.openai.com/v1 \\
        --api_key sk-your-key \\
        --capabilities general,code,analysis
    
    \b
      # Add a model with streaming enabled
      ai-config model add \\
        --name deepseek-chat \\
        --api https://api.deepseek.com/v1 \\
        --api_key sk-your-key \\
        --provider deepseek \\
        --streaming true
    
    \b
      # Add a model and set it as default
      ai-config model add \\
        --name deepseek-chat \\
        --api https://api.deepseek.com/v1 \\
        --api_key sk-your-key \\
        --provider deepseek \\
        --default
    """
    # Build model data
    model_data = {
        'name': name,
        'api_base': api,
        'provider': provider,
        'priority': priority,
        'timeout': timeout,
        'stream_timeout': stream_timeout,
        'max_retries': max_retries,
        'supports_streaming': streaming,
    }
    
    if api_key:
        model_data['api_key'] = api_key
    
    if instance_id:
        model_data['instance_id'] = instance_id
    
    # Parse capabilities
    model_data['capabilities'] = ModelValidator.parse_capabilities(capabilities)
    
    # Normalize data
    normalized_data = ModelValidator.normalize_model_data(model_data)
    
    # Validate
    validator = ModelValidator()
    is_valid, errors, warnings = validator.validate(normalized_data)
    
    # Show warnings
    for warning in warnings:
        Output.warning(warning)
    
    # Check validation result
    if not is_valid:
        Output.validation_errors(errors)
        sys.exit(Output.EXIT_VALIDATION_ERROR)
    
    # If dry-run, just show what would be added
    if dry_run:
        Output.info("Dry run - model would be added with the following configuration:")
        Output.model_info(normalized_data)
        sys.exit(Output.EXIT_SUCCESS)
    
    # Add model
    from sysai_framework.core.status_codes import MODEL_ALREADY_EXISTS
    
    def online_mode(client):
        """Execute via D-Bus (service running)"""
        result = _add_model_via_dbus(normalized_data, force, set_as_default)
        
        if result.success:
            Output.success(result.get_message())
            if result.data:
                Output.info(f"Instance ID: {result.data}")
            if set_as_default:
                Output.info("Model has been set as the default model")
            Output.success("Configuration is now active")
            return 0
        else:
            # Use status code instead of string matching
            if result.status == MODEL_ALREADY_EXISTS and not force:
                Output.error(result.get_message())
                Output.info("Use --force to overwrite the existing model")
                return result.status.cli_exit_code
            else:
                Output.error(result.get_message())
                return result.status.cli_exit_code
    
    def offline_mode():
        """Execute in offline mode (direct file access)"""
        result = _add_model_offline(
            normalized_data, force, config_path, set_as_default
        )
        
        if result.success:
            Output.success(result.get_message())
            if result.data:
                Output.info(f"Instance ID: {result.data.instance_id}")
            if set_as_default:
                Output.info("Model has been set as the default model")
            return 0
        else:
            # Use status code instead of string matching
            if result.status == MODEL_ALREADY_EXISTS and not force:
                Output.error(result.get_message())
                Output.info("Use --force to overwrite the existing model")
                return result.status.cli_exit_code
            else:
                Output.error(result.get_message())
                return result.status.cli_exit_code
    
    # Auto-execute based on service status
    exit_code = auto_execute(
        online_func=online_mode,
        offline_func=offline_mode,
        operation_name="add model",
        require_config_file=True,
        config_path=config_path
    )
    
    sys.exit(exit_code)


@model.command('list')
@click.option('--config_path', default=DEFAULT_CONFIG_PATH,
              help=f'Configuration file path (default: {DEFAULT_CONFIG_PATH})')
@click.option('--json', 'as_json', is_flag=True, help='Output as JSON')
def list_models(config_path: str, as_json: bool):
    """List all configured models"""
    
    def online_mode(client):
        """Execute via D-Bus (service running)"""
        models = client.list_models()
        # Sanitize sensitive information (D-Bus should already handle this, but be safe)
        return Output.sanitize_sensitive_data(models) if models else models
    
    def offline_mode():
        """Execute in offline mode (direct file access)"""
        from sysai_framework.config import ModelConfigManager
        
        if not os.path.exists(config_path):
            Output.error(f"Configuration file not found: {config_path}")
            sys.exit(Output.EXIT_CONFIG_NOT_FOUND)
        
        # In CLI offline mode, don't allow creating default config to avoid reading default configs
        manager = ModelConfigManager(config_path=config_path, allow_create_default=False)
        models = [
            {
                'name': m.name,
                'instance_id': m.instance_id,
                'provider': m.provider,
                'api_base': m.api_base,
                'api_key': '***' if m.api_key else None,  # Sanitize sensitive information
                'priority': m.priority,
                'capabilities': m.capabilities,
                'supports_streaming': m.supports_streaming,
                'timeout': m.timeout if m.timeout is not None else 'inherit (routing)',
                'stream_timeout': m.stream_timeout if m.stream_timeout is not None else 'inherit (timeout)',
                'max_retries': m.max_retries,
                'is_healthy': m.is_healthy,
            }
            for m in manager.models.values()
        ]
        return models
    
    # Auto-execute based on service status
    try:
        models = auto_execute(
            online_func=online_mode,
            offline_func=offline_mode,
            operation_name="list models",
            require_config_file=True,
            config_path=config_path,
            silent_offline=True  # Read-only operation, don't show warnings
        )
        
        if not models:
            Output.info("No models configured")
            sys.exit(Output.EXIT_SUCCESS)
        
        if as_json:
            Output.json_output(models)
        else:
            # Table output
            headers = ['Name', 'Instance ID', 'Provider', 'Priority', 'Healthy']
            rows = []
            for model in models:
                instance_id = model.get('instance_id', 'auto')
                if instance_id and len(instance_id) > 16:
                    instance_id = instance_id[:16] + '...'
                rows.append([
                    model.get('name', 'N/A'),
                    instance_id,
                    model.get('provider', 'openai_like'),
                    str(model.get('priority', 1)),
                    'Yes' if model.get('is_healthy', True) else 'No'
                ])
            
            Output.table(headers, rows)
        
        sys.exit(Output.EXIT_SUCCESS)
        
    except Exception as e:
        Output.error(f"Failed to list models: {e}")
        sys.exit(Output.EXIT_CONFIG_NOT_FOUND)


@model.command('show')
@click.argument('identifier', required=False)
@click.option('--name', help='Model name to show')
@click.option('--instance_id', help='Instance ID to show')
@click.option('--config_path', default=DEFAULT_CONFIG_PATH,
              help=f'Configuration file path (default: {DEFAULT_CONFIG_PATH})')
@click.option('--json', 'as_json', is_flag=True, help='Output as JSON')
def show_model(identifier: Optional[str], name: Optional[str], instance_id: Optional[str], config_path: str, as_json: bool):
    """
    Show details of a specific model
    
    You can specify the model using:
    - IDENTIFIER (positional argument): Model name or instance_id (will match both)
    - --name: Model name
    - --instance_id: Instance ID
    - --name and --instance_id: Both (will show matching models)
    
    If options are provided, IDENTIFIER is ignored.
    If IDENTIFIER is used, it will match both by name and instance_id, merging all results.
    """
    
    # Parameter validation: at least one must be provided
    if not identifier and not name and not instance_id:
        Output.error("At least one of IDENTIFIER, --name, or --instance_id must be provided")
        sys.exit(Output.EXIT_VALIDATION_ERROR)
    
    # Helper function to convert model config to dict
    def _model_to_dict(model_config) -> dict:
        """Convert ModelConfig to dictionary format"""
        return {
            'name': model_config.name,
            'instance_id': model_config.instance_id,
            'provider': model_config.provider,
            'api_base': model_config.api_base,
            'api_key': '***' if model_config.api_key else None,
            'priority': model_config.priority,
            'capabilities': model_config.capabilities,
            'supports_streaming': model_config.supports_streaming,
            'timeout': model_config.timeout if model_config.timeout is not None else 'inherit (routing)',
            'stream_timeout': model_config.stream_timeout if model_config.stream_timeout is not None else 'inherit (timeout)',
            'max_retries': model_config.max_retries,
            'is_healthy': model_config.is_healthy,
        }
    
    def online_mode(client):
        """Execute via D-Bus (service running)"""
        matching = []
        seen_instance_ids = set()  # For deduplication
        
        def add_result(result):
            """Helper to add result to matching list with deduplication and sanitization"""
            if not result:
                return
            if isinstance(result, list):
                for m in result:
                    inst_id = m.get('instance_id')
                    if inst_id and inst_id not in seen_instance_ids:
                        # Sanitize sensitive information before adding
                        sanitized = Output.sanitize_sensitive_data(m)
                        matching.append(sanitized)
                        seen_instance_ids.add(inst_id)
            else:
                inst_id = result.get('instance_id')
                if inst_id and inst_id not in seen_instance_ids:
                    # Sanitize sensitive information before adding
                    sanitized = Output.sanitize_sensitive_data(result)
                    matching.append(sanitized)
                    seen_instance_ids.add(inst_id)
        
        # If options are provided, use them (ignore identifier)
        if name or instance_id:
            # If both are provided, validate they match
            if name and instance_id:
                # Get model by instance_id first
                result = client.get_model(instance_id)
                if not result:
                    # Return special marker to indicate instance_id not found
                    return [{'__error__': 'instance_id_not_found', 'instance_id': instance_id}]
                
                # Parse result (could be dict or list)
                if isinstance(result, list):
                    if len(result) == 0:
                        return [{'__error__': 'instance_id_not_found', 'instance_id': instance_id}]
                    model = result[0]
                else:
                    model = result
                
                # Check if name matches
                if model.get('name') != name:
                    # Return special marker to indicate name mismatch
                    return [{'__error__': 'name_mismatch', 'instance_id': instance_id, 'expected_name': name, 'actual_name': model.get('name')}]
                
                # Names match, return the model (sanitize sensitive information)
                sanitized = Output.sanitize_sensitive_data(model)
                matching.append(sanitized)
                seen_instance_ids.add(model.get('instance_id'))
            else:
                # Only one option provided
                if name:
                    result = client.get_model(name)
                    add_result(result)
                
                if instance_id:
                    result = client.get_model(instance_id)
                    add_result(result)
        else:
            # Use identifier: D-Bus GetModel tries name first, then instance_id
            # Note: If identifier is both a name and an instance_id, D-Bus will only
            # return results by name (since it tries name first). This is a limitation
            # of the D-Bus interface. For full support, use --name and --instance_id options.
            if identifier:
                result = client.get_model(identifier)
                add_result(result)
        
        return matching
    
    def offline_mode():
        """Execute in offline mode (direct file access)"""
        from sysai_framework.config import ModelConfigManager
        
        if not os.path.exists(config_path):
            Output.error(f"Configuration file not found: {config_path}")
            sys.exit(Output.EXIT_CONFIG_NOT_FOUND)
        
        # In CLI offline mode, don't allow creating default config to avoid reading default configs
        manager = ModelConfigManager(config_path=config_path, allow_create_default=False)
        
        matching = []
        seen_instance_ids = set()  # For deduplication
        
        # If options are provided, use them (ignore identifier)
        if name or instance_id:
            # If both are provided, validate they match
            if name and instance_id:
                model = manager.get_model_by_instance_id(instance_id)
                if not model:
                    # Return special marker to indicate instance_id not found
                    return [{'__error__': 'instance_id_not_found', 'instance_id': instance_id}]
                
                # Check if name matches
                if model.name != name:
                    # Return special marker to indicate name mismatch
                    return [{'__error__': 'name_mismatch', 'instance_id': instance_id, 'expected_name': name, 'actual_name': model.name}]
                
                # Names match, return the model
                matching.append(_model_to_dict(model))
                seen_instance_ids.add(model.instance_id)
            else:
                # Only one option provided
                if name:
                    models_by_name = manager.get_models_by_name(name)
                    for m in models_by_name:
                        if m.instance_id not in seen_instance_ids:
                            matching.append(_model_to_dict(m))
                            seen_instance_ids.add(m.instance_id)
                
                if instance_id:
                    model = manager.get_model_by_instance_id(instance_id)
                    if model and model.instance_id not in seen_instance_ids:
                        matching.append(_model_to_dict(model))
                        seen_instance_ids.add(model.instance_id)
        else:
            # Use identifier: match both by name and instance_id, merge results
            if identifier:
                # Try by name
                models_by_name = manager.get_models_by_name(identifier)
                for m in models_by_name:
                    if m.instance_id not in seen_instance_ids:
                        matching.append(_model_to_dict(m))
                        seen_instance_ids.add(m.instance_id)
                
                # Try by instance_id (if not already found)
                if identifier not in seen_instance_ids:
                    model = manager.get_model_by_instance_id(identifier)
                    if model and model.instance_id not in seen_instance_ids:
                        matching.append(_model_to_dict(model))
                        seen_instance_ids.add(model.instance_id)
        
        return matching
    
    # Determine the search term for error messages
    search_term = identifier if identifier else (name if name else instance_id)
    
    # Auto-execute based on service status
    try:
        matching = auto_execute(
            online_func=online_mode,
            offline_func=offline_mode,
            operation_name="show model",
            require_config_file=True,
            config_path=config_path,
            silent_offline=True  # Read-only operation, don't show warnings
        )
        
        # Check for error markers (from validation failures)
        if matching and len(matching) == 1 and isinstance(matching[0], dict) and matching[0].get('__error__'):
            error_info = matching[0]
            error_type = error_info.get('__error__')
            
            if error_type == 'instance_id_not_found':
                Output.error(f"Model with instance_id '{error_info.get('instance_id')}' not found")
                sys.exit(Output.EXIT_VALIDATION_ERROR)
            elif error_type == 'name_mismatch':
                Output.error(f"Model name mismatch: instance_id '{error_info.get('instance_id')}' belongs to model '{error_info.get('actual_name')}', not '{error_info.get('expected_name')}'")
                sys.exit(Output.EXIT_VALIDATION_ERROR)
        
        if not matching:
            Output.error(f"Model not found: {search_term}")
            sys.exit(Output.EXIT_VALIDATION_ERROR)
        
        if as_json:
            Output.json_output(matching if len(matching) > 1 else matching[0])
        else:
            for i, model in enumerate(matching):
                if i > 0:
                    click.echo("")  # Separator
                Output.model_info(model)
        
        sys.exit(Output.EXIT_SUCCESS)
        
    except Exception as e:
        Output.error(f"Failed to get model: {e}")
        sys.exit(Output.EXIT_CONFIG_NOT_FOUND)


@model.command('update')
@click.option('--name', help='Model name to update')
@click.option('--instance_id', help='Instance ID to update')
@click.option('--priority', default=None, type=int, callback=lambda ctx, param, val: val if val is None else _validate_priority(ctx, param, val),
              help='New priority (1-100)')
@click.option('--capabilities', default=None,
              help='New capabilities (comma-separated, e.g., general,code,analysis)')
@click.option('--timeout', default=None, type=int, callback=lambda ctx, param, val: val if val is None else _validate_timeout(ctx, param, val),
              help='New timeout in seconds (3-3600). None means inherit from routing timeout')
@click.option('--stream_timeout', default=None, type=int, callback=lambda ctx, param, val: val if val is None else _validate_stream_timeout(ctx, param, val),
              help='New streaming inter-chunk timeout in seconds (3-3600). None means inherit from timeout')
@click.option('--max_retries', default=None, type=int, callback=lambda ctx, param, val: val if val is None else _validate_max_retries(ctx, param, val),
              help='New max retry attempts (0-10)')
@click.option('--provider', default=None,
              help='New provider type: openai, deepseek, dashscope, moonshot, ollama, openai_like, volcengine, zai, minimax, azure')
@click.option('--streaming', default=None, type=_parse_bool_option,
              help='Enable/disable streaming: true/false')
@click.option('--config_path', default=DEFAULT_CONFIG_PATH,
              help=f'Configuration file path (default: {DEFAULT_CONFIG_PATH})')
@click.option('--dry_run', is_flag=True, help='Show changes without applying them')
def update_model(
    name: Optional[str],
    instance_id: Optional[str],
    priority: Optional[int],
    capabilities: Optional[str],
    timeout: Optional[int],
    stream_timeout: Optional[int],
    max_retries: Optional[int],
    provider: Optional[str],
    streaming: Optional[bool],
    config_path: str,
    dry_run: bool
):
    """
    Update model configuration (partial update)

    At least one of --name or --instance_id must be provided to identify the model.
    Only specified fields will be updated; others remain unchanged.

    If --name is provided and multiple instances share that name,
    --instance_id must also be provided to disambiguate.

    Examples:

    \b
      # Update priority by name
      ai-config model update --name deepseek-chat --priority 50

    \b
      # Update multiple fields by instance_id
      ai-config model update --instance_id abc123 \\
        --timeout 60 --max-retries 5

    \b
      # Preview changes without applying
      ai-config model update --name deepseek-chat --priority 10 --dry-run
    """
    # Step 1: Validate identifier arguments
    if not name and not instance_id:
        Output.error("At least one of --name or --instance_id must be provided")
        sys.exit(Output.EXIT_VALIDATION_ERROR)

    # Step 2: Build updates dict (filter out None values)
    updates = {}
    if priority is not None:
        updates['priority'] = priority
    if capabilities is not None:
        updates['capabilities'] = ModelValidator.parse_capabilities(capabilities)
    if timeout is not None:
        updates['timeout'] = timeout
    if stream_timeout is not None:
        updates['stream_timeout'] = stream_timeout
    if max_retries is not None:
        updates['max_retries'] = max_retries
    if provider is not None:
        updates['provider'] = provider
    if streaming is not None:
        updates['supports_streaming'] = streaming

    if not updates:
        Output.error("No fields to update. Specify at least one field to change")
        sys.exit(Output.EXIT_VALIDATION_ERROR)

    # Step 3: Helper to resolve instance_id from name
    def _resolve_instance_id(manager_or_client, is_dbus=False):
        """Resolve name to instance_id, returns instance_id or None."""
        if instance_id:
            return instance_id

        # Only name provided - must resolve to single instance
        if is_dbus:
            result = manager_or_client.get_model(name)
            if not result:
                return None
            if isinstance(result, list):
                matching = result
            else:
                matching = [result]
        else:
            matching = manager_or_client.get_models_by_name(name)

        if not matching:
            return None

        if len(matching) > 1:
            Output.error(f"Multiple models found with name '{name}':")
            for m in matching:
                if is_dbus:
                    Output.info(f"  Instance ID: {m.get('instance_id')}, Provider: {m.get('provider')}")
                else:
                    Output.info(f"  Instance ID: {m.instance_id}, Provider: {m.provider}")
            Output.info("Use --instance_id to specify which instance to update")
            return '__MULTIPLE__'

        if is_dbus:
            return matching[0].get('instance_id')
        else:
            return matching[0].instance_id

    def _resolve_and_validate_dbus(client):
        """Resolve and validate in D-Bus mode. Returns instance_id or None."""
        resolved_id = _resolve_instance_id(client, is_dbus=True)
        if resolved_id is None:
            Output.error(f"Model '{name}' not found")
            return None
        if resolved_id == '__MULTIPLE__':
            return None
        return resolved_id

    def _resolve_and_validate_offline(manager):
        """Resolve and validate in offline mode. Returns instance_id or None."""
        resolved_id = _resolve_instance_id(manager, is_dbus=False)
        if resolved_id is None:
            Output.error(f"Model '{name}' not found")
            return None
        if resolved_id == '__MULTIPLE__':
            return None

        # Validate name+instance_id match if both provided
        if name and instance_id:
            model = manager.get_model_by_instance_id(instance_id)
            if model and model.name != name:
                Output.error(
                    f"Model name mismatch: instance_id '{instance_id}' "
                    f"belongs to model '{model.name}', not '{name}'"
                )
                return None

        return resolved_id

    # Step 4: Dry-run mode
    if dry_run:
        def offline_show():
            from sysai_framework.config import ModelConfigManager

            if not os.path.exists(config_path):
                Output.error(f"Configuration file not found: {config_path}")
                return None

            manager = ModelConfigManager(config_path=config_path, allow_create_default=False)
            resolved_id = _resolve_and_validate_offline(manager)
            if not resolved_id:
                return None

            model = manager.get_model_by_instance_id(resolved_id)
            return model

        model = offline_show()
        if model is None:
            sys.exit(Output.EXIT_VALIDATION_ERROR)

        # Show pending changes
        Output.info(f"Dry run - changes for model '{model.name}' (instance_id: {model.instance_id}):")
        for field, new_value in updates.items():
            current = getattr(model, field, None)
            if field == 'capabilities' and isinstance(current, list):
                current = ', '.join(current)
            if isinstance(new_value, list):
                display_value = ', '.join(new_value)
            else:
                display_value = new_value
            Output.info(f"  {field}: {current} -> {display_value}")

        sys.exit(Output.EXIT_SUCCESS)

    # Step 5: Execute update
    def online_mode(client):
        """Execute via D-Bus (service running)"""
        from sysai_framework.core.status_codes import NO_CHANGE

        resolved_id = _resolve_and_validate_dbus(client)
        if not resolved_id:
            return Output.EXIT_VALIDATION_ERROR

        # Validate name+instance_id match if both provided
        if name and instance_id:
            model_result = client.get_model(instance_id)
            if model_result:
                if isinstance(model_result, list):
                    model_info = model_result[0] if model_result else {}
                else:
                    model_info = model_result
                if model_info.get('name') != name:
                    Output.error(
                        f"Model name mismatch: instance_id '{instance_id}' "
                        f"belongs to model '{model_info.get('name')}', not '{name}'"
                    )
                    return Output.EXIT_VALIDATION_ERROR

        result = client.update_model(resolved_id, updates)

        if result.success:
            msg = result.get_message()
            Output.success(msg)
            model_data = result.details.get('model', {})
            if model_data:
                changed = result.details.get('updated_fields', [])
                if changed:
                    Output.info(f"Updated fields: {', '.join(changed)}")
            return 0
        elif result.status == NO_CHANGE:
            Output.info(result.get_message())
            return 0
        else:
            Output.error(result.get_message())
            return result.status.cli_exit_code

    def offline_mode():
        """Execute in offline mode (direct file access)"""
        from sysai_framework.config import ModelConfigManager

        if not os.path.exists(config_path):
            Output.error(f"Configuration file not found: {config_path}")
            return Output.EXIT_CONFIG_NOT_FOUND

        manager = ModelConfigManager(config_path=config_path, allow_create_default=False)
        resolved_id = _resolve_and_validate_offline(manager)
        if not resolved_id:
            return Output.EXIT_VALIDATION_ERROR

        result = manager.update_model(resolved_id, updates, persist=True)

        if result.success:
            msg = result.get_message()
            Output.success(msg)
            changed = result.details.get('updated_fields', [])
            if changed:
                Output.info(f"Updated fields: {', '.join(changed)}")
            return 0
        else:
            from sysai_framework.core.status_codes import NO_CHANGE
            if result.status == NO_CHANGE:
                Output.info(result.get_message())
                return 0
            Output.error(result.get_message())
            return result.status.cli_exit_code

    exit_code = auto_execute(
        online_func=online_mode,
        offline_func=offline_mode,
        operation_name="update model",
        require_config_file=True,
        config_path=config_path
    )

    sys.exit(exit_code)


@model.command('remove')
@click.option('--name', help='Model name to remove')
@click.option('--instance_id', help='Instance ID to remove')
@click.option('--all', 'remove_all', is_flag=True, help='Remove all models with the same name (only valid with --name)')
@click.option('--config_path', default=DEFAULT_CONFIG_PATH,
              help=f'Configuration file path (default: {DEFAULT_CONFIG_PATH})')
@click.option('-y', '--yes', 'skip_confirm', is_flag=True, help='Skip confirmation prompt')
def remove_model(name: Optional[str], instance_id: Optional[str], remove_all: bool, config_path: str, skip_confirm: bool):
    """
    Remove a model by name or instance_id
    
    At least one of --name or --instance_id must be provided.
    If both are provided, they must match (the instance_id must belong to a model with the given name).
    If only --name is provided and multiple models with the same name exist, use --all to remove all of them.
    """
    
    # Parameter validation
    if not name and not instance_id:
        Output.error("At least one of --name or --instance_id must be provided")
        sys.exit(Output.EXIT_VALIDATION_ERROR)
    
    if remove_all and not name:
        Output.error("--all option can only be used with --name")
        sys.exit(Output.EXIT_VALIDATION_ERROR)
    
    def online_mode(client):
        """Execute via D-Bus (service running)"""
        from sysai_framework.core.status_codes import MODEL_NOT_FOUND
        
        # If both name and instance_id are provided, validate they match
        if name and instance_id:
            # Get model by instance_id first
            model_result = client.get_model(instance_id)
            if not model_result:
                Output.error(f"Model with instance_id '{instance_id}' not found")
                return Output.EXIT_VALIDATION_ERROR
            
            # Parse result (could be dict or list)
            if isinstance(model_result, list):
                if len(model_result) == 0:
                    Output.error(f"Model with instance_id '{instance_id}' not found")
                    return Output.EXIT_VALIDATION_ERROR
                model = model_result[0]
            else:
                model = model_result
            
            # Check if name matches
            if model.get('name') != name:
                Output.error(f"Model name mismatch: instance_id '{instance_id}' belongs to model '{model.get('name')}', not '{name}'")
                return Output.EXIT_VALIDATION_ERROR
            
            # Check if it's the default model (for pre-deletion prompt)
            routing_config = client.get_routing_config()
            is_default_before = (
                routing_config.get('default_model_instance_id') == instance_id or
                routing_config.get('default_model') == model.get('name')
            )
            
            # Confirmation prompt
            if not skip_confirm:
                prompt_msg = f"Are you sure you want to remove model '{name}' (instance_id: {instance_id})?"
                if is_default_before:
                    prompt_msg += " (This is the current default model)"
                if not click.confirm(prompt_msg):
                    return Output.EXIT_SUCCESS
            
            # Remove model
            result = client.remove_model(instance_id)
            if result.success:
                Output.success(result.get_message())
                if is_default_before:
                    Output.warning("The default model has been cleared. Use 'ai-config routing set-default --instance_id <instance_id>' to set a new default model.")
                return 0
            else:
                Output.error(result.get_message())
                return result.status.cli_exit_code
        
        # Only instance_id provided
        if instance_id and not name:
            # Check if it's the default model (for pre-deletion prompt)
            routing_config = client.get_routing_config()
            is_default_before = (routing_config.get('default_model_instance_id') == instance_id)
            
            # Get model info if it's the default by name
            if not is_default_before:
                model_info = client.get_model(instance_id)
                if model_info:
                    if isinstance(model_info, list) and len(model_info) > 0:
                        model_info = model_info[0]
                    if isinstance(model_info, dict):
                        is_default_before = (routing_config.get('default_model') == model_info.get('name'))
            
            # Confirmation prompt
            if not skip_confirm:
                prompt_msg = f"Are you sure you want to remove model with instance_id '{instance_id}'?"
                if is_default_before:
                    prompt_msg += " (This is the current default model)"
                if not click.confirm(prompt_msg):
                    return Output.EXIT_SUCCESS
            
            # Remove model
            result = client.remove_model(instance_id)
            if result.success:
                Output.success(result.get_message())
                if is_default_before:
                    Output.warning("The default model has been cleared. Use 'ai-config routing set-default --instance_id <instance_id>' to set a new default model.")
                return 0
            else:
                Output.error(result.get_message())
                return result.status.cli_exit_code
        
        # Only name provided (or name + remove_all)
        if name and not instance_id:
            # Get models by name
            models_result = client.get_model(name)
            if not models_result:
                Output.error(f"Model with name '{name}' not found")
                return Output.EXIT_VALIDATION_ERROR
            
            # Parse result
            if isinstance(models_result, list):
                matching_models = models_result
            else:
                matching_models = [models_result]
            
            if len(matching_models) == 0:
                Output.error(f"Model with name '{name}' not found")
                return Output.EXIT_VALIDATION_ERROR
            
            if len(matching_models) > 1 and not remove_all:
                Output.error(f"Multiple models found with name '{name}':")
                for m in matching_models:
                    Output.info(f"  Instance ID: {m.get('instance_id')}, Provider: {m.get('provider')}, API: {m.get('api_base')}")
                Output.info("Use --instance_id to specify a specific instance, or --all to remove all of them")
                return Output.EXIT_VALIDATION_ERROR
            
            # Check if any model is default (for pre-deletion prompt)
            routing_config = client.get_routing_config()
            contains_default = any(
                routing_config.get('default_model_instance_id') == m.get('instance_id') or
                routing_config.get('default_model') == m.get('name')
                for m in matching_models
            )
            
            # Confirmation prompt
            if not skip_confirm:
                if len(matching_models) > 1:
                    prompt_msg = f"Are you sure you want to remove {len(matching_models)} model(s) with name '{name}'?"
                    if contains_default:
                        prompt_msg += " (This includes the current default model)"
                    if not click.confirm(prompt_msg):
                        return Output.EXIT_SUCCESS
                else:
                    prompt_msg = f"Are you sure you want to remove model '{name}'?"
                    if contains_default:
                        prompt_msg += " (This is the current default model)"
                    if not click.confirm(prompt_msg):
                        return Output.EXIT_SUCCESS
            
            # Remove all matching models
            success_count = 0
            failed_count = 0
            for model in matching_models:
                model_instance_id = model.get('instance_id')
                if not model_instance_id:
                    failed_count += 1
                    continue
                
                result = client.remove_model(model_instance_id)
                if result.success:
                    success_count += 1
                else:
                    failed_count += 1
                    Output.error(f"Failed to remove model {model_instance_id}: {result.get_message()}")
            
            if failed_count == 0:
                if len(matching_models) > 1:
                    Output.success(f"Successfully removed {success_count} model(s) with name '{name}'")
                else:
                    Output.success(f"Model '{name}' removed successfully")
                
                if contains_default:
                    Output.warning("The default model has been cleared. Use 'ai-config routing set-default --instance_id <instance_id>' to set a new default model.")
                return 0
            else:
                return Output.EXIT_WRITE_FAILED
    
    def offline_mode():
        """Execute in offline mode (direct file access)"""
        from sysai_framework.config import ModelConfigManager
        
        if not os.path.exists(config_path):
            Output.error(f"Configuration file not found: {config_path}")
            sys.exit(Output.EXIT_CONFIG_NOT_FOUND)
        
        # In CLI offline mode, don't allow creating default config to avoid reading default configs
        manager = ModelConfigManager(config_path=config_path, allow_create_default=False)
        
        # If both name and instance_id are provided, validate they match
        if name and instance_id:
            model = manager.get_model_by_instance_id(instance_id)
            if not model:
                Output.error(f"Model with instance_id '{instance_id}' not found")
                sys.exit(Output.EXIT_VALIDATION_ERROR)
            
            if model.name != name:
                Output.error(f"Model name mismatch: instance_id '{instance_id}' belongs to model '{model.name}', not '{name}'")
                sys.exit(Output.EXIT_VALIDATION_ERROR)
            
            # Check if it's the default model (for pre-deletion prompt)
            is_default_before = (
                manager.default_model_instance_id == instance_id or 
                manager.default_model == model.name
            )
            
            # Confirmation prompt
            if not skip_confirm:
                prompt_msg = f"Are you sure you want to remove model '{name}' (instance_id: {instance_id})?"
                if is_default_before:
                    prompt_msg += " (This is the current default model)"
                if not click.confirm(prompt_msg):
                    sys.exit(Output.EXIT_SUCCESS)
            
            # Remove model
            is_default = manager._remove_model_from_memory(instance_id)
            _remove_model_from_file(instance_id, config_path, clear_default=is_default)
            
            # Post-deletion message
            Output.success("Model removed successfully")
            if is_default:
                Output.info("The default model has been cleared. Use 'ai-config routing set-default --name <model_name>' to set a new default model.")
            return 0
        
        # Only instance_id provided
        if instance_id and not name:
            if instance_id not in manager.models:
                Output.error(f"Model with instance_id '{instance_id}' not found")
                sys.exit(Output.EXIT_VALIDATION_ERROR)
            
            model = manager.get_model_by_instance_id(instance_id)
            
            # Check if it's the default model (for pre-deletion prompt)
            is_default_before = (
                manager.default_model_instance_id == instance_id or 
                (model and manager.default_model == model.name)
            )
            
            # Confirmation prompt
            if not skip_confirm:
                prompt_msg = f"Are you sure you want to remove model with instance_id '{instance_id}'?"
                if is_default_before:
                    prompt_msg += " (This is the current default model)"
                if not click.confirm(prompt_msg):
                    sys.exit(Output.EXIT_SUCCESS)
            
            # Remove model
            is_default = manager._remove_model_from_memory(instance_id)
            _remove_model_from_file(instance_id, config_path, clear_default=is_default)
            
            # Post-deletion message
            Output.success("Model removed successfully")
            if is_default:
                Output.info("The default model has been cleared. Use 'ai-config routing set-default --name <model_name>' to set a new default model.")
            return 0
        
        # Only name provided (or name + remove_all)
        if name and not instance_id:
            matching_models = manager.get_models_by_name(name)
            if not matching_models:
                Output.error(f"Model with name '{name}' not found")
                sys.exit(Output.EXIT_VALIDATION_ERROR)
            
            if len(matching_models) > 1 and not remove_all:
                Output.error(f"Multiple models found with name '{name}':")
                for m in matching_models:
                    Output.info(f"  Instance ID: {m.instance_id}, Provider: {m.provider}, API: {m.api_base}")
                Output.info("Use --instance_id to specify a specific instance, or --all to remove all of them")
                sys.exit(Output.EXIT_VALIDATION_ERROR)
            
            # Check if any model is default (for pre-deletion prompt)
            contains_default = any(
                manager.default_model_instance_id == m.instance_id or 
                manager.default_model == m.name 
                for m in matching_models
            )
            
            # Confirmation prompt
            if not skip_confirm:
                if len(matching_models) > 1:
                    prompt_msg = f"Are you sure you want to remove {len(matching_models)} model(s) with name '{name}'?"
                    if contains_default:
                        prompt_msg += " (This includes the current default model)"
                    if not click.confirm(prompt_msg):
                        sys.exit(Output.EXIT_SUCCESS)
                else:
                    prompt_msg = f"Are you sure you want to remove model '{name}'?"
                    if contains_default:
                        prompt_msg += " (This is the current default model)"
                    if not click.confirm(prompt_msg):
                        sys.exit(Output.EXIT_SUCCESS)
            
            # Remove all matching models
            removed_count = 0
            any_was_default = False
            for model in matching_models:
                model_instance_id = model.instance_id
                is_default = manager._remove_model_from_memory(model_instance_id)
                _remove_model_from_file(model_instance_id, config_path, clear_default=is_default)
                if is_default:
                    any_was_default = True
                removed_count += 1
            
            # Post-deletion message
            if len(matching_models) > 1:
                Output.success(f"Successfully removed {removed_count} model(s) with name '{name}'")
            else:
                Output.success(f"Model '{name}' removed successfully")
            
            if any_was_default:
                Output.info("The default model has been cleared. Use 'ai-config routing set-default --name <model_name>' to set a new default model.")
            return 0
    
    # Auto-execute based on service status
    try:
        exit_code = auto_execute(
            online_func=online_mode,
            offline_func=offline_mode,
            operation_name="remove model",
            require_config_file=True,
            config_path=config_path
        )
        sys.exit(exit_code)
    except Exception as e:
        Output.error(f"Failed to remove model: {e}")
        sys.exit(Output.EXIT_WRITE_FAILED)


def _remove_model_from_file(instance_id: str, config_path: str, clear_default: bool = False) -> None:
    """
    Remove model from configuration file
    
    Args:
        instance_id: Instance ID of the model to remove
        config_path: Path to configuration file
        clear_default: If True, also clear default_model and default_model_instance_id
    """
    from ruamel.yaml import YAML
    
    if not os.path.exists(config_path):
        return
    
    yaml_obj = YAML()
    yaml_obj.preserve_quotes = True
    
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml_obj.load(f)
    
    if config and 'models' in config:
        models = config['models']
        for i in range(len(models) - 1, -1, -1):
            if models[i].get('instance_id') == instance_id:
                del models[i]
                break
        
        # Clear default model if needed
        if clear_default and 'routing' in config:
            config['routing']['default_model'] = None
            config['routing']['default_model_instance_id'] = None
        
        with open(config_path, 'w', encoding='utf-8') as f:
            yaml_obj.dump(config, f)
