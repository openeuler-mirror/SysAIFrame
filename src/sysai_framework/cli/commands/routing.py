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


# Health Check Status Command definition
def _define_health_check_status_command(health_check_group):
    """Define and return the health_check status click command"""
    @health_check_group.command('status')
    @click.option('--json', 'json_output', is_flag=True,
                  help='Output in JSON format')
    def health_check_status(json_output: bool):
        """Display health check configuration and model health status"""

        def online_mode(client):
            """Execute via D-Bus"""
            return _health_check_status_online(client, json_output)

        def offline_mode():
            """Execute in offline mode"""
            return _health_check_status_offline()

        exit_code = auto_execute(
            online_func=online_mode,
            offline_func=offline_mode,
            operation_name="get health check status",
            require_config_file=False,
            config_path=None
        )

        sys.exit(exit_code)

    return health_check_status


# Health Check Trigger Command - online_mode
def _health_check_trigger_online(client, model_name):
    """Trigger health check via D-Bus"""
    try:
        success, message = client.trigger_health_check(model_name or "")

        if success:
            Output.success(message)
            return 0
        else:
            Output.error(message)
            return 1

    except Exception as e:
        Output.error(f"Failed to trigger health check: {e}")
        return 1


# Health Check Trigger Command - offline_mode
def _health_check_trigger_offline():
    """Trigger health check in offline mode"""
    Output.error("Cannot trigger health check in offline mode")
    Output.info("Please start the service and try again")
    return 1


# Health Check Trigger Command definition
def _define_health_check_trigger_command(health_check_group):
    """Define and return the health_check trigger click command"""
    @health_check_group.command('trigger')
    @click.argument('model_name', required=False)
    def health_check_trigger(model_name: Optional[str]):
        """Manually trigger health check for specified model or all models"""

        def online_mode(client):
            """Execute via D-Bus"""
            return _health_check_trigger_online(client, model_name)

        def offline_mode():
            """Execute in offline mode"""
            return _health_check_trigger_offline()

        exit_code = auto_execute(
            online_func=online_mode,
            offline_func=offline_mode,
            operation_name="trigger health check",
            require_config_file=False,
            config_path=None
        )

        sys.exit(exit_code)

    return health_check_trigger


# Lightweight Health Check Subgroup definition
def _define_lightweight_group(health_check_group):
    """Define and return the lightweight health check subgroup"""
    @health_check_group.group('lightweight')
    def lightweight():
        """Lightweight health check management"""
        pass
    return lightweight


# Lightweight Enable Command - online_mode
def _lightweight_enable_online(client):
    """Enable lightweight health check via D-Bus"""
    import json as json_module
    try:
        config = {"lightweight_enabled": True}
        success, message = client.update_health_check_config(json_module.dumps(config))

        if success:
            Output.success("Lightweight health check enabled")
            return 0
        else:
            Output.error(message)
            return 1

    except Exception as e:
        Output.error(f"Failed to enable lightweight check: {e}")
        return 1


# Lightweight Disable Command - online_mode
def _lightweight_disable_online(client):
    """Disable lightweight health check via D-Bus"""
    import json as json_module
    try:
        config = {"lightweight_enabled": False}
        success, message = client.update_health_check_config(json_module.dumps(config))

        if success:
            Output.success("Lightweight health check disabled")
            return 0
        else:
            Output.error(message)
            return 1

    except Exception as e:
        Output.error(f"Failed to disable lightweight check: {e}")
        return 1


# Lightweight Set-Interval Command - online_mode
def _lightweight_set_interval_online(client, seconds):
    """Set lightweight health check interval via D-Bus"""
    import json as json_module
    try:
        config = {"lightweight_interval": seconds}
        success, message = client.update_health_check_config(json_module.dumps(config))

        if success:
            Output.success(f"Lightweight check interval set to {seconds}s")
            return 0
        else:
            Output.error(message)
            return 1

    except Exception as e:
        Output.error(f"Failed to set interval: {e}")
        return 1


# Lightweight offline_mode helper
def _lightweight_offline_mode(operation):
    """Generic offline_mode for lightweight commands"""
    Output.error(f"Cannot {operation} lightweight check in offline mode")
    Output.info("Please start the service and try again")
    return 1


# Lightweight Enable Command definition
def _define_lightweight_enable_command(lightweight_group):
    """Define and return the lightweight enable click command"""
    @lightweight_group.command('enable')
    def lightweight_enable():
        """Enable lightweight health check"""
        def online_mode(client):
            return _lightweight_enable_online(client)
        def offline_mode():
            return _lightweight_offline_mode("enable")

        exit_code = auto_execute(
            online_func=online_mode,
            offline_func=offline_mode,
            operation_name="enable lightweight check",
            require_config_file=False,
            config_path=None
        )
        sys.exit(exit_code)
    return lightweight_enable


# Lightweight Disable Command definition
def _define_lightweight_disable_command(lightweight_group):
    """Define and return the lightweight disable click command"""
    @lightweight_group.command('disable')
    def lightweight_disable():
        """Disable lightweight health check"""
        def online_mode(client):
            return _lightweight_disable_online(client)
        def offline_mode():
            return _lightweight_offline_mode("disable")

        exit_code = auto_execute(
            online_func=online_mode,
            offline_func=offline_mode,
            operation_name="disable lightweight check",
            require_config_file=False,
            config_path=None
        )
        sys.exit(exit_code)
    return lightweight_disable


# Lightweight Set-Interval Command definition
def _define_lightweight_set_interval_command(lightweight_group):
    """Define and return the lightweight set-interval click command"""
    @lightweight_group.command('set-interval')
    @click.argument('seconds', type=int)
    def lightweight_set_interval(seconds: int):
        """Set lightweight health check interval in seconds"""
        if seconds <= 0:
            Output.error("Interval must be a positive integer")
            sys.exit(Output.EXIT_VALIDATION_ERROR)

        def online_mode(client):
            return _lightweight_set_interval_online(client, seconds)
        def offline_mode():
            return _lightweight_offline_mode("set interval for")

        exit_code = auto_execute(
            online_func=online_mode,
            offline_func=offline_mode,
            operation_name="set lightweight interval",
            require_config_file=False,
            config_path=None
        )
        sys.exit(exit_code)
    return lightweight_set_interval


# Actual Request Health Check Subgroup definition
def _define_actual_request_group(health_check_group):
    """Define and return the actual-request health check subgroup"""
    @health_check_group.group('actual-request')
    def actual_request():
        """Actual request validation management"""
        pass
    return actual_request


# Actual Request Enable Command - online_mode
def _actual_request_enable_online(client, interval):
    """Enable actual request validation via D-Bus"""
    import json as json_module
    try:
        config = {
            "actual_request_enabled": True,
            "actual_request_interval": interval
        }
        success, message = client.update_health_check_config(json_module.dumps(config))

        if success:
            Output.success(f"Actual request validation enabled (interval: {interval}s)")
            return 0
        else:
            Output.error(message)
            return 1

    except Exception as e:
        Output.error(f"Failed to enable actual request validation: {e}")
        return 1


# Actual Request Disable Command - online_mode
def _actual_request_disable_online(client):
    """Disable actual request validation via D-Bus"""
    import json as json_module
    try:
        config = {"actual_request_enabled": False}
        success, message = client.update_health_check_config(json_module.dumps(config))

        if success:
            Output.success("Actual request validation disabled")
            return 0
        else:
            Output.error(message)
            return 1

    except Exception as e:
        Output.error(f"Failed to disable actual request validation: {e}")
        return 1


# Actual Request Set-Interval Command - online_mode
def _actual_request_set_interval_online(client, seconds):
    """Set actual request validation interval via D-Bus"""
    import json as json_module
    try:
        config = {"actual_request_interval": seconds}
        success, message = client.update_health_check_config(json_module.dumps(config))

        if success:
            Output.success(f"Actual request interval set to {seconds}s")
            return 0
        else:
            Output.error(message)
            return 1

    except Exception as e:
        Output.error(f"Failed to set interval: {e}")
        return 1


# Actual Request offline_mode helper
def _actual_request_offline_mode(operation):
    """Generic offline_mode for actual_request commands"""
    Output.error(f"Cannot {operation} actual request validation in offline mode")
    Output.info("Please start the service and try again")
    return 1


# Actual Request Enable Command definition
def _define_actual_request_enable_command(actual_request_group):
    """Define and return the actual_request enable click command"""
    @actual_request_group.command('enable')
    @click.option('--interval', type=int, default=300,
                  help='Check interval in seconds (default: 300)')
    def actual_request_enable(interval: int):
        """Enable actual request validation (WARNING: incurs API costs)"""
        if interval <= 0:
            Output.error("Interval must be a positive integer")
            sys.exit(Output.EXIT_VALIDATION_ERROR)

        Output.warning("WARNING: Enabling actual request validation will incur API costs!")

        def online_mode(client):
            return _actual_request_enable_online(client, interval)
        def offline_mode():
            return _actual_request_offline_mode("enable")

        exit_code = auto_execute(
            online_func=online_mode,
            offline_func=offline_mode,
            operation_name="enable actual request validation",
            require_config_file=False,
            config_path=None
        )
        sys.exit(exit_code)
    return actual_request_enable


# Actual Request Disable Command definition
def _define_actual_request_disable_command(actual_request_group):
    """Define and return the actual_request disable click command"""
    @actual_request_group.command('disable')
    def actual_request_disable():
        """Disable actual request validation"""
        def online_mode(client):
            return _actual_request_disable_online(client)
        def offline_mode():
            return _actual_request_offline_mode("disable")

        exit_code = auto_execute(
            online_func=online_mode,
            offline_func=offline_mode,
            operation_name="disable actual request validation",
            require_config_file=False,
            config_path=None
        )
        sys.exit(exit_code)
    return actual_request_disable


# Actual Request Set-Interval Command definition
def _define_actual_request_set_interval_command(actual_request_group):
    """Define and return the actual_request set-interval click command"""
    @actual_request_group.command('set-interval')
    @click.argument('seconds', type=int)
    def actual_request_set_interval(seconds: int):
        """Set actual request validation interval in seconds"""
        if seconds <= 0:
            Output.error("Interval must be a positive integer")
            sys.exit(Output.EXIT_VALIDATION_ERROR)

        def online_mode(client):
            return _actual_request_set_interval_online(client, seconds)
        def offline_mode():
            return _actual_request_offline_mode("set interval for")

        exit_code = auto_execute(
            online_func=online_mode,
            offline_func=offline_mode,
            operation_name="set actual request interval",
            require_config_file=False,
            config_path=None
        )
        sys.exit(exit_code)
    return actual_request_set_interval


# Health Check Set-Timeout Command - online_mode
def _health_check_set_timeout_online(client, seconds):
    """Set health check timeout via D-Bus"""
    import json as json_module
    try:
        config = {"timeout": seconds}
        success, message = client.update_health_check_config(json_module.dumps(config))

        if success:
            Output.success(f"Health check timeout set to {seconds}s")
            return 0
        else:
            Output.error(message)
            return 1

    except Exception as e:
        Output.error(f"Failed to set timeout: {e}")
        return 1


# Health Check Set-Timeout Command - offline_mode
def _health_check_set_timeout_offline():
    """Set health check timeout in offline mode"""
    Output.error("Cannot set timeout in offline mode")
    Output.info("Please start the service and try again")
    return 1


# Health Check Set-Timeout Command definition
def _define_health_check_set_timeout_command(health_check_group):
    """Define and return the health_check set-timeout click command"""
    @health_check_group.command('set-timeout')
    @click.argument('seconds', type=int)
    def health_check_set_timeout(seconds: int):
        """Set health check timeout in seconds"""
        if seconds <= 0:
            Output.error("Timeout must be a positive integer")
            sys.exit(Output.EXIT_VALIDATION_ERROR)

        def online_mode(client):
            return _health_check_set_timeout_online(client, seconds)
        def offline_mode():
            return _health_check_set_timeout_offline()

        exit_code = auto_execute(
            online_func=online_mode,
            offline_func=offline_mode,
            operation_name="set health check timeout",
            require_config_file=False,
            config_path=None
        )
        sys.exit(exit_code)
    return health_check_set_timeout


# Retry Policy Command Group definition
def _define_retry_group(routing_group):
    """Define and return the retry click group"""
    @routing_group.group(name='retry')
    def retry():
        """Retry policy management commands"""
        pass
    return retry


# Retry Status Command - online_mode
def _retry_status_online(client, json_output):
    """Get retry policy status via D-Bus"""
    import json as json_module

    try:
        config_json = client.get_retry_policy_config()
        config = json_module.loads(config_json)

        if json_output:
            Output.print_json(config)
            return 0

        Output.section("Retry Policy Configuration")
        Output.info(f"  Max Attempts: {config.get('max_attempts')}")
        Output.info(f"  Backoff Factor: {config.get('backoff_factor')}")
        Output.info(f"  Base Delay: {config.get('base_delay')}s")
        Output.info(f"  Max Delay: {config.get('max_delay')}s")

        return 0

    except Exception as e:
        Output.error(f"Failed to get retry policy: {e}")
        return 1
