"""
Copyright (C) 2025 CTyunOS. All Rights Reserved.
File: cli/commands/routing.py
Desc: CLI commands for routing configuration
Date: 2025-11-27
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


@click.group(name='routing')
def routing():
    """Routing configuration management commands"""
    pass


# set-default command - parameter validation
def _set_default_validate_params(name, instance_id):
    """Validate set-default command parameters"""
    if not name and not instance_id:
        Output.error("At least one of --name or --instance_id must be provided")
        return Output.EXIT_VALIDATION_ERROR
    return None


# set-default command - online_mode with name and instance_id
def _set_default_online_name_instance_id(name, instance_id, client):
    """Handle set-default online_mode when both name and instance_id are provided"""
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

    # Names match, proceed with setting default
    result = client.set_default_model(name, instance_id)
    if result.success:
        Output.success(result.get_message())
        Output.info(f"Default model: {name}")
        Output.info(f"Instance ID: {instance_id}")
        return 0
    else:
        Output.error(result.get_message())
        if result.details and 'available_models' in result.details:
            Output.info(f"Available models: {', '.join(result.details['available_models'])}")
        return result.status.cli_exit_code if hasattr(result, 'status') else 1


# set-default command - online_mode with instance_id only
def _set_default_online_instance_id_only(instance_id, client):
    """Handle set-default online_mode when only instance_id is provided"""
    # Get model by instance_id to get the name
    model_result = client.get_model(instance_id)
    if not model_result:
        Output.error(f"Model with instance_id '{instance_id}' not found")
        return Output.EXIT_VALIDATION_ERROR

    # Parse result
    if isinstance(model_result, list):
        if len(model_result) == 0:
            Output.error(f"Model with instance_id '{instance_id}' not found")
            return Output.EXIT_VALIDATION_ERROR
        model = model_result[0]
    else:
        model = model_result

    model_name = model.get('name')
    if not model_name:
        Output.error(f"Failed to get model name for instance_id '{instance_id}'")
        return Output.EXIT_VALIDATION_ERROR

    result = client.set_default_model(model_name, instance_id)
    if result.success:
        Output.success(result.get_message())
        Output.info(f"Default model: {model_name}")
        Output.info(f"Instance ID: {instance_id}")
        return 0
    else:
        Output.error(result.get_message())
        if result.details and 'available_models' in result.details:
            Output.info(f"Available models: {', '.join(result.details['available_models'])}")
        return result.status.cli_exit_code if hasattr(result, 'status') else 1


# set-default command - online_mode with name only
def _set_default_online_name_only(name, client):
    """Handle set-default online_mode when only name is provided"""
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

    if len(matching_models) > 1:
        Output.error(f"Multiple models found with name '{name}':")
        for m in matching_models:
            Output.info(f"  Instance ID: {m.get('instance_id')}, Provider: {m.get('provider')}, API: {m.get('api_base')}")
        Output.info("Use --instance_id to specify a specific instance")
        return Output.EXIT_VALIDATION_ERROR

    # Only one model found, use it
    model = matching_models[0]
    model_instance_id = model.get('instance_id')
    if not model_instance_id:
        Output.error(f"Failed to get instance_id for model '{name}'")
        return Output.EXIT_VALIDATION_ERROR

    result = client.set_default_model(name, model_instance_id)
    if result.success:
        Output.success(result.get_message())
        Output.info(f"Default model: {name}")
        Output.info(f"Instance ID: {model_instance_id}")
        return 0
    else:
        Output.error(result.get_message())
        if result.details and 'available_models' in result.details:
            Output.info(f"Available models: {', '.join(result.details['available_models'])}")
        return result.status.cli_exit_code if hasattr(result, 'status') else 1


# set-default command - offline_mode with name and instance_id
def _set_default_offline_name_instance_id(name, instance_id, config_manager):
    """Handle set-default offline_mode when both name and instance_id are provided"""
    model = config_manager.get_model_by_instance_id(instance_id)
    if not model:
        Output.error(f"Model with instance_id '{instance_id}' not found")
        return Output.EXIT_VALIDATION_ERROR

    if model.name != name:
        Output.error(f"Model name mismatch: instance_id '{instance_id}' belongs to model '{model.name}', not '{name}'")
        return Output.EXIT_VALIDATION_ERROR

    # Names match, proceed with setting default
    result = config_manager.set_default_model(
        model_name=name,
        instance_id=instance_id,
        persist=True,
        require_file_lock=True
    )

    if result.success:
        Output.success(result.get_message())
        Output.info(f"Default model: {name}")
        Output.info(f"Instance ID: {instance_id}")
        return 0
    else:
        Output.error(result.get_message())
        if result.details:
            if 'available_models' in result.details:
                Output.info(f"Available models: {', '.join(result.details['available_models'])}")
            if 'available_instances' in result.details:
                Output.info(f"Available instances: {', '.join(result.details['available_instances'])}")
        return 1


# set-default command - offline_mode with instance_id only
def _set_default_offline_instance_id_only(instance_id, config_manager):
    """Handle set-default offline_mode when only instance_id is provided"""
    model = config_manager.get_model_by_instance_id(instance_id)
    if not model:
        Output.error(f"Model with instance_id '{instance_id}' not found")
        return Output.EXIT_VALIDATION_ERROR

    result = config_manager.set_default_model(
        model_name=model.name,
        instance_id=instance_id,
        persist=True,
        require_file_lock=True
    )

    if result.success:
        Output.success(result.get_message())
        Output.info(f"Default model: {model.name}")
        Output.info(f"Instance ID: {instance_id}")
        return 0
    else:
        Output.error(result.get_message())
        if result.details:
            if 'available_models' in result.details:
                Output.info(f"Available models: {', '.join(result.details['available_models'])}")
            if 'available_instances' in result.details:
                Output.info(f"Available instances: {', '.join(result.details['available_instances'])}")
        return 1


# set-default command - offline_mode with name only
def _set_default_offline_name_only(name, config_manager):
    """Handle set-default offline_mode when only name is provided"""
    models = config_manager.get_models_by_name(name)
    if not models:
        Output.error(f"Model with name '{name}' not found")
        return Output.EXIT_VALIDATION_ERROR

    if len(models) > 1:
        Output.error(f"Multiple models found with name '{name}':")
        for m in models:
            Output.info(f"  Instance ID: {m.instance_id}, Provider: {m.provider}, API: {m.api_base}")
        Output.info("Use --instance_id to specify a specific instance")
        return Output.EXIT_VALIDATION_ERROR

    # Only one model found, use it
    model = models[0]
    result = config_manager.set_default_model(
        model_name=name,
        instance_id=model.instance_id,
        persist=True,
        require_file_lock=True
    )

    if result.success:
        Output.success(result.get_message())
        Output.info(f"Default model: {name}")
        Output.info(f"Instance ID: {model.instance_id}")
        return 0
    else:
        Output.error(result.get_message())
        if result.details:
            if 'available_models' in result.details:
                Output.info(f"Available models: {', '.join(result.details['available_models'])}")
            if 'available_instances' in result.details:
                Output.info(f"Available instances: {', '.join(result.details['available_instances'])}")
        return 1


# set-default command - online_mode dispatcher
def _set_default_online_dispatcher(name, instance_id, client):
    """Dispatch to appropriate online_mode handler based on provided parameters"""
    if name and instance_id:
        return _set_default_online_name_instance_id(name, instance_id, client)
    elif instance_id and not name:
        return _set_default_online_instance_id_only(instance_id, client)
    elif name and not instance_id:
        return _set_default_online_name_only(name, client)
    return None


# set-default command - offline_mode dispatcher
def _set_default_offline_dispatcher(name, instance_id, config_manager):
    """Dispatch to appropriate offline_mode handler based on provided parameters"""
    if name and instance_id:
        return _set_default_offline_name_instance_id(name, instance_id, config_manager)
    elif instance_id and not name:
        return _set_default_offline_instance_id_only(instance_id, config_manager)
    elif name and not instance_id:
        return _set_default_offline_name_only(name, config_manager)
    return None


# set-default command definition
def _define_set_default_command(routing_group):
    """Define and return the set-default click command"""
    @routing_group.command('set-default')
    @click.option('--name', help='Model name to set as default')
    @click.option('--instance_id', help='Instance ID to set as default')
    @click.option('--config_path', 'config_file',
                  help=f'Configuration file path (default: {DEFAULT_CONFIG_PATH})')
    def set_default(name: Optional[str], instance_id: Optional[str], config_file: Optional[str]):
        """
        Set default model for routing

        At least one of --name or --instance_id must be provided.
        If only --name is provided and multiple models with the same name exist, you must specify --instance_id.
        If both are provided, they must match (the instance_id must belong to a model with the given name).

        Examples:
            ai-config routing set-default --name qwen
            ai-config routing set-default --name qwen --instance_id qwen_1
            ai-config routing set-default --instance_id qwen_1
            ai-config routing set-default --name moonshot --config_path /path/to/config.yaml
        """
        from sysai_framework.config.model_config import ModelConfigManager
        from sysai_framework.cli.constants import DEFAULT_CONFIG_PATH

        # Parameter validation
        validation_result = _set_default_validate_params(name, instance_id)
        if validation_result is not None:
            sys.exit(validation_result)

        # Use default config path if not specified
        if not config_file:
            config_file = DEFAULT_CONFIG_PATH

        def online_mode(client):
            """Execute via D-Bus (service running)"""
            return _set_default_online_dispatcher(name, instance_id, client)

        def offline_mode():
            """Execute in offline mode (direct file access)"""
            try:
                # In CLI offline mode, don't allow creating default config
                config_manager = ModelConfigManager(config_path=config_file, allow_create_default=False)
                return _set_default_offline_dispatcher(name, instance_id, config_manager)
            except Exception as e:
                Output.error(f"Failed to set default model: {e}")
                logger.error(f"Offline mode failed: {e}", exc_info=True)
                return 1

        # Auto-execute based on service status
        exit_code = auto_execute(
            online_func=online_mode,
            offline_func=offline_mode,
            operation_name="set default model",
            require_config_file=True,
            config_path=config_file
        )

        sys.exit(exit_code)

    return set_default


# Health Check Command Group
def _define_health_check_group(routing_group):
    """Define and return the health_check click group"""
    @routing_group.group(name='health-check')
    def health_check():
        """Health check management commands"""
        pass
    return health_check


# Health Check Status Command - online_mode
def _health_check_status_online(client, json_output):
    """Get health check status via D-Bus"""
    import json as json_module

    try:
        config_json = client.get_health_check_config()
        config = json_module.loads(config_json)

        status_json = client.get_health_status("")
        status = json_module.loads(status_json)

        if json_output:
            Output.print_json({
                "config": config,
                "status": status
            })
            return 0

        Output.section("Health Check Configuration")
        Output.info(f"  Lightweight Check: {'Enabled' if config.get('lightweight_enabled') else 'Disabled'}")
        Output.info(f"  Lightweight Interval: {config.get('lightweight_interval')}s")
        Output.info(f"  Actual Request Check: {'Enabled' if config.get('actual_request_enabled') else 'Disabled'}")
        Output.info(f"  Actual Request Interval: {config.get('actual_request_interval')}s")
        Output.info(f"  Timeout: {config.get('timeout')}s")

        Output.section("Model Health Status")
        total = status.get("total_models", 0)
        healthy = status.get("healthy_models", 0)
        unhealthy = status.get("unhealthy_models", 0)

        Output.info(f"  Total Models: {total}")
        Output.success(f"  Healthy: {healthy}")
        if unhealthy > 0:
            Output.error(f"  Unhealthy: {unhealthy}")

        for model in status.get("models", []):
            name = model.get("name")
            is_healthy = model.get("is_healthy")
            reason = model.get("unhealthy_reason", "none")

            if is_healthy:
                Output.success(f"    {name}: Healthy")
            else:
                Output.error(f"    {name}: Unhealthy (reason: {reason})")

        return 0

    except Exception as e:
        Output.error(f"Failed to get health check status: {e}")
        return 1


# Health Check Status Command - offline_mode
def _health_check_status_offline():
    """Get health check status in offline mode"""
    Output.warning("Offline mode: Cannot get real-time health status")
    Output.info("Please start the service to view health check status")
    return 1
