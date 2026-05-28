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


@routing.command('set-default')
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
    if not name and not instance_id:
        Output.error("At least one of --name or --instance_id must be provided")
        sys.exit(Output.EXIT_VALIDATION_ERROR)
    
    # Use default config path if not specified
    if not config_file:
        config_file = DEFAULT_CONFIG_PATH
    
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
        
        # Only instance_id provided
        if instance_id and not name:
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
        
        # Only name provided
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
    
    def offline_mode():
        """Execute in offline mode (direct file access)"""
        try:
            # In CLI offline mode, don't allow creating default config to avoid reading default configs
            config_manager = ModelConfigManager(config_path=config_file, allow_create_default=False)
            
            # If both name and instance_id are provided, validate they match
            if name and instance_id:
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
            
            # Only instance_id provided
            if instance_id and not name:
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
            
            # Only name provided
            if name and not instance_id:
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
            
            # If neither name nor instance_id provided, error
            if not name and not instance_id:
                Output.error("Either --name or --instance_id must be provided")
                return Output.EXIT_VALIDATION_ERROR
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


# ===== Health Check Command Group =====

@routing.group(name='health-check')
def health_check():
    """Health check management commands"""
    pass


@health_check.command('status')
@click.option('--json', 'json_output', is_flag=True, 
              help='Output in JSON format')
def health_check_status(json_output: bool):
    """Display health check configuration and model health status"""
    
    def online_mode(client):
        """Execute via D-Bus"""
        import json as json_module
        
        try:
            # Get health check configuration
            config_json = client.get_health_check_config()
            config = json_module.loads(config_json)
            
            # Get health status for all models
            status_json = client.get_health_status("")
            status = json_module.loads(status_json)
            
            if json_output:
                Output.print_json({
                    "config": config,
                    "status": status
                })
                return 0
            
            # Display configuration
            Output.section("Health Check Configuration")
            Output.info(f"  Lightweight Check: {'Enabled' if config.get('lightweight_enabled') else 'Disabled'}")
            Output.info(f"  Lightweight Interval: {config.get('lightweight_interval')}s")
            Output.info(f"  Actual Request Check: {'Enabled' if config.get('actual_request_enabled') else 'Disabled'}")
            Output.info(f"  Actual Request Interval: {config.get('actual_request_interval')}s")
            Output.info(f"  Timeout: {config.get('timeout')}s")
            
            # Display model health status
            Output.section("Model Health Status")
            total = status.get("total_models", 0)
            healthy = status.get("healthy_models", 0)
            unhealthy = status.get("unhealthy_models", 0)
            
            Output.info(f"  Total Models: {total}")
            Output.success(f"  Healthy: {healthy}")
            if unhealthy > 0:
                Output.error(f"  Unhealthy: {unhealthy}")
            
            # Display per-model status
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
    
    def offline_mode():
        """Execute in offline mode"""
        Output.warning("Offline mode: Cannot get real-time health status")
        Output.info("Please start the service to view health check status")
        return 1
    
    exit_code = auto_execute(
        online_func=online_mode,
        offline_func=offline_mode,
        operation_name="get health check status",
        require_config_file=False,
        config_path=None
    )
    
    sys.exit(exit_code)


@health_check.command('trigger')
@click.argument('model_name', required=False)
def health_check_trigger(model_name: Optional[str]):
    """Manually trigger health check for specified model or all models"""
    
    def online_mode(client):
        """Execute via D-Bus"""
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
    
    def offline_mode():
        """Execute in offline mode"""
        Output.error("Cannot trigger health check in offline mode")
        Output.info("Please start the service and try again")
        return 1
    
    exit_code = auto_execute(
        online_func=online_mode,
        offline_func=offline_mode,
        operation_name="trigger health check",
        require_config_file=False,
        config_path=None
    )
    
    sys.exit(exit_code)


@health_check.group('lightweight')
def lightweight():
    """Lightweight health check management"""
    pass


@lightweight.command('enable')
def lightweight_enable():
    """Enable lightweight health check"""
    import json as json_module
    
    def online_mode(client):
        """Execute via D-Bus"""
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
    
    def offline_mode():
        """Execute in offline mode"""
        Output.error("Cannot enable lightweight check in offline mode")
        Output.info("Please start the service and try again")
        return 1
    
    exit_code = auto_execute(
        online_func=online_mode,
        offline_func=offline_mode,
        operation_name="enable lightweight check",
        require_config_file=False,
        config_path=None
    )
    
    sys.exit(exit_code)


@lightweight.command('disable')
def lightweight_disable():
    """Disable lightweight health check"""
    import json as json_module
    
    def online_mode(client):
        """Execute via D-Bus"""
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
    
    def offline_mode():
        """Execute in offline mode"""
        Output.error("Cannot disable lightweight check in offline mode")
        Output.info("Please start the service and try again")
        return 1
    
    exit_code = auto_execute(
        online_func=online_mode,
        offline_func=offline_mode,
        operation_name="disable lightweight check",
        require_config_file=False,
        config_path=None
    )
    
    sys.exit(exit_code)


@lightweight.command('set-interval')
@click.argument('seconds', type=int)
def lightweight_set_interval(seconds: int):
    """Set lightweight health check interval in seconds"""
    import json as json_module
    
    if seconds < 1 or seconds > 3600:
        Output.error("Interval must be between 1 and 3600 seconds")
        sys.exit(Output.EXIT_VALIDATION_ERROR)

    def online_mode(client):
        """Execute via D-Bus"""
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
    
    def offline_mode():
        """Execute in offline mode"""
        Output.error("Cannot set interval in offline mode")
        Output.info("Please start the service and try again")
        return 1
    
    exit_code = auto_execute(
        online_func=online_mode,
        offline_func=offline_mode,
        operation_name="set lightweight interval",
        require_config_file=False,
        config_path=None
    )
    
    sys.exit(exit_code)


@health_check.group('actual-request')
def actual_request():
    """Actual request validation management"""
    pass


@actual_request.command('enable')
@click.option('--interval', type=int, default=300,
              help='Check interval in seconds (default: 300)')
def actual_request_enable(interval: int):
    """Enable actual request validation (WARNING: incurs API costs)"""
    import json as json_module
    
    if interval < 60 or interval > 86400:
        Output.error("Interval must be between 60 and 86400 seconds")
        sys.exit(Output.EXIT_VALIDATION_ERROR)
    
    Output.warning("WARNING: Enabling actual request validation will incur API costs!")
    
    def online_mode(client):
        """Execute via D-Bus"""
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
    
    def offline_mode():
        """Execute in offline mode"""
        Output.error("Cannot enable actual request validation in offline mode")
        Output.info("Please start the service and try again")
        return 1
    
    exit_code = auto_execute(
        online_func=online_mode,
        offline_func=offline_mode,
        operation_name="enable actual request validation",
        require_config_file=False,
        config_path=None
    )
    
    sys.exit(exit_code)


@actual_request.command('disable')
def actual_request_disable():
    """Disable actual request validation"""
    import json as json_module
    
    def online_mode(client):
        """Execute via D-Bus"""
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
    
    def offline_mode():
        """Execute in offline mode"""
        Output.error("Cannot disable actual request validation in offline mode")
        Output.info("Please start the service and try again")
        return 1
    
    exit_code = auto_execute(
        online_func=online_mode,
        offline_func=offline_mode,
        operation_name="disable actual request validation",
        require_config_file=False,
        config_path=None
    )
    
    sys.exit(exit_code)


@actual_request.command('set-interval')
@click.argument('seconds', type=int)
def actual_request_set_interval(seconds: int):
    """Set actual request validation interval in seconds"""
    import json as json_module
    
    if seconds < 60 or seconds > 86400:
        Output.error("Interval must be between 60 and 86400 seconds")
        sys.exit(Output.EXIT_VALIDATION_ERROR)

    def online_mode(client):
        """Execute via D-Bus"""
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
    
    def offline_mode():
        """Execute in offline mode"""
        Output.error("Cannot set interval in offline mode")
        Output.info("Please start the service and try again")
        return 1
    
    exit_code = auto_execute(
        online_func=online_mode,
        offline_func=offline_mode,
        operation_name="set actual request interval",
        require_config_file=False,
        config_path=None
    )
    
    sys.exit(exit_code)


@health_check.command('set-timeout')
@click.argument('seconds', type=int)
def health_check_set_timeout(seconds: int):
    """Set health check timeout in seconds"""
    import json as json_module
    
    if seconds < 1 or seconds > 300:
        Output.error("Timeout must be between 1 and 300 seconds")
        sys.exit(Output.EXIT_VALIDATION_ERROR)
    
    def online_mode(client):
        """Execute via D-Bus"""
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
    
    def offline_mode():
        """Execute in offline mode"""
        Output.error("Cannot set timeout in offline mode")
        Output.info("Please start the service and try again")
        return 1
    
    exit_code = auto_execute(
        online_func=online_mode,
        offline_func=offline_mode,
        operation_name="set health check timeout",
        require_config_file=False,
        config_path=None
    )
    
    sys.exit(exit_code)


# ===== Retry Policy Command Group =====

@routing.group(name='retry')
def retry():
    """Retry policy management commands"""
    pass


@retry.command('status')
@click.option('--json', 'json_output', is_flag=True, 
              help='Output in JSON format')
def retry_status(json_output: bool):
    """Display current retry policy configuration"""
    
    def online_mode(client):
        """Execute via D-Bus"""
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
    
    def offline_mode():
        """Execute in offline mode"""
        Output.warning("Offline mode: Cannot get real-time configuration")
        Output.info("Please start the service to view retry policy")
        return 1
    
    exit_code = auto_execute(
        online_func=online_mode,
        offline_func=offline_mode,
        operation_name="get retry policy",
        require_config_file=False,
        config_path=None
    )
    
    sys.exit(exit_code)


@retry.command('set-attempts')
@click.argument('attempts', type=int)
def retry_set_attempts(attempts: int):
    """Set maximum retry attempts"""
    import json as json_module
    
    if attempts < 1 or attempts > 10:
        Output.error("Attempts must be between 1 and 10")
        sys.exit(Output.EXIT_VALIDATION_ERROR)
    
    def online_mode(client):
        """Execute via D-Bus"""
        try:
            config = {"max_attempts": attempts}
            success, message = client.update_retry_policy_config(json_module.dumps(config))
            
            if success:
                Output.success(f"Max retry attempts set to {attempts}")
                return 0
            else:
                Output.error(message)
                return 1
                
        except Exception as e:
            Output.error(f"Failed to set retry attempts: {e}")
            return 1
    
    def offline_mode():
        """Execute in offline mode"""
        Output.error("Cannot set retry attempts in offline mode")
        Output.info("Please start the service and try again")
        return 1
    
    exit_code = auto_execute(
        online_func=online_mode,
        offline_func=offline_mode,
        operation_name="set retry attempts",
        require_config_file=False,
        config_path=None
    )
    
    sys.exit(exit_code)


@retry.command('set-backoff')
@click.argument('factor', type=int)
def retry_set_backoff(factor: int):
    """Set backoff factor for exponential backoff"""
    import json as json_module
    
    if factor < 1 or factor > 10:
        Output.error("Backoff factor must be between 1 and 10")
        sys.exit(Output.EXIT_VALIDATION_ERROR)
    
    def online_mode(client):
        """Execute via D-Bus"""
        try:
            config = {"backoff_factor": factor}
            success, message = client.update_retry_policy_config(json_module.dumps(config))
            
            if success:
                Output.success(f"Backoff factor set to {factor}")
                return 0
            else:
                Output.error(message)
                return 1
                
        except Exception as e:
            Output.error(f"Failed to set backoff factor: {e}")
            return 1
    
    def offline_mode():
        """Execute in offline mode"""
        Output.error("Cannot set backoff factor in offline mode")
        Output.info("Please start the service and try again")
        return 1
    
    exit_code = auto_execute(
        online_func=online_mode,
        offline_func=offline_mode,
        operation_name="set backoff factor",
        require_config_file=False,
        config_path=None
    )
    
    sys.exit(exit_code)


@retry.command('set-base-delay')
@click.argument('seconds', type=int)
def retry_set_base_delay(seconds: int):
    """Set base delay for first retry in seconds"""
    import json as json_module
    
    if seconds < 1 or seconds > 60:
        Output.error("Base delay must be between 1 and 60 seconds")
        sys.exit(Output.EXIT_VALIDATION_ERROR)
    
    def online_mode(client):
        """Execute via D-Bus"""
        try:
            config = {"base_delay": seconds}
            success, message = client.update_retry_policy_config(json_module.dumps(config))
            
            if success:
                Output.success(f"Base delay set to {seconds}s")
                return 0
            else:
                Output.error(message)
                return 1
                
        except Exception as e:
            Output.error(f"Failed to set base delay: {e}")
            return 1
    
    def offline_mode():
        """Execute in offline mode"""
        Output.error("Cannot set base delay in offline mode")
        Output.info("Please start the service and try again")
        return 1
    
    exit_code = auto_execute(
        online_func=online_mode,
        offline_func=offline_mode,
        operation_name="set base delay",
        require_config_file=False,
        config_path=None
    )
    
    sys.exit(exit_code)


@retry.command('set-max-delay')
@click.argument('seconds', type=int)
def retry_set_max_delay(seconds: int):
    """Set maximum delay cap in seconds"""
    import json as json_module
    
    if seconds < 1 or seconds > 300:
        Output.error("Max delay must be between 1 and 300 seconds")
        sys.exit(Output.EXIT_VALIDATION_ERROR)
    
    def online_mode(client):
        """Execute via D-Bus"""
        try:
            config = {"max_delay": seconds}
            success, message = client.update_retry_policy_config(json_module.dumps(config))
            
            if success:
                Output.success(f"Max delay set to {seconds}s")
                return 0
            else:
                Output.error(message)
                return 1
                
        except Exception as e:
            Output.error(f"Failed to set max delay: {e}")
            return 1
    
    def offline_mode():
        """Execute in offline mode"""
        Output.error("Cannot set max delay in offline mode")
        Output.info("Please start the service and try again")
        return 1
    
    exit_code = auto_execute(
        online_func=online_mode,
        offline_func=offline_mode,
        operation_name="set max delay",
        require_config_file=False,
        config_path=None
    )
    
    sys.exit(exit_code)


# ===== Runtime Mode Command Group =====

@routing.command('show')
@click.option('--json', 'json_output', is_flag=True,
              help='Output in JSON format')
@click.option('--config_path', 'config_file',
              help=f'Configuration file path (default: {DEFAULT_CONFIG_PATH})')
def routing_show(json_output: bool, config_file: Optional[str]):
    """Display complete routing configuration including runtime mode and load balance settings"""
    from sysai_framework.config.model_config import ModelConfigManager
    from sysai_framework.cli.constants import DEFAULT_CONFIG_PATH
    
    if not config_file:
        config_file = DEFAULT_CONFIG_PATH
    
    def online_mode(client):
        """Execute via D-Bus"""
        import json as json_module
        
        try:
            # Get routing config
            routing = client.get_routing_config()
            
            # Get runtime mode
            mode = client.get_runtime_mode()
            strategy = client.get_load_balance_strategy()
            
            if json_output:
                result = {
                    "mode": mode,
                    "load_balance": {
                        "strategy": strategy
                    },
                    "default_model": routing.get('default_model'),
                    "default_model_instance_id": routing.get('default_model_instance_id')
                }
                Output.print_json(result)
                return 0
            
            Output.section("Runtime Mode Configuration")
            Output.info(f"  Mode: {mode}")
            
            if mode == "load-balance":
                Output.section("Load Balance Configuration")
                Output.info(f"  Strategy: {strategy}")
            
            Output.section("Default Model")
            Output.info(f"  Model: {routing.get('default_model', 'None')}")
            if routing.get('default_model_instance_id'):
                Output.info(f"  Instance ID: {routing.get('default_model_instance_id')}")
            
            return 0
            
        except Exception as e:
            Output.error(f"Failed to get routing config: {e}")
            return 1
    
    def offline_mode():
        """Execute in offline mode"""
        try:
            config_manager = ModelConfigManager(config_path=config_file, allow_create_default=False)
            runtime_config = config_manager.routing_config.runtime
            
            if json_output:
                import json as json_module
                result = {
                    "mode": runtime_config.mode,
                    "load_balance": {
                        "strategy": runtime_config.load_balance.strategy,
                        "options": {
                            "latency_buffer": runtime_config.load_balance.options.latency_buffer,
                            "latency_window": runtime_config.load_balance.options.latency_window,
                            "usage_window": runtime_config.load_balance.options.usage_window
                        }
                    },
                    "default_model": config_manager.default_model,
                    "default_model_instance_id": config_manager.default_model_instance_id
                }
                Output.print_json(result)
                return 0
            
            Output.section("Runtime Mode Configuration")
            Output.info(f"  Mode: {runtime_config.mode}")
            
            if runtime_config.mode == "load-balance":
                Output.section("Load Balance Configuration")
                Output.info(f"  Strategy: {runtime_config.load_balance.strategy}")
                Output.info(f"  Options:")
                Output.info(f"    Latency Buffer: {runtime_config.load_balance.options.latency_buffer}")
                Output.info(f"    Latency Window: {runtime_config.load_balance.options.latency_window}")
                Output.info(f"    Usage Window: {runtime_config.load_balance.options.usage_window}s")
            
            Output.section("Default Model")
            Output.info(f"  Model: {config_manager.default_model or 'None'}")
            if config_manager.default_model_instance_id:
                Output.info(f"  Instance ID: {config_manager.default_model_instance_id}")
            
            return 0
            
        except Exception as e:
            Output.error(f"Failed to get routing config: {e}")
            logger.error(f"Offline mode failed: {e}", exc_info=True)
            return 1
    
    exit_code = auto_execute(
        online_func=online_mode,
        offline_func=offline_mode,
        operation_name="show routing config",
        require_config_file=True,
        config_path=config_file,
        silent_offline=json_output,
    )
    
    sys.exit(exit_code)


@routing.command('set-mode')
@click.option('--mode', required=True, type=click.Choice(['default', 'load-balance']),
              help='Runtime mode: default or load-balance')
@click.option('--config_path', 'config_file',
              help=f'Configuration file path (default: {DEFAULT_CONFIG_PATH})')
def routing_set_mode(mode: str, config_file: Optional[str]):
    """Set runtime mode (default or load-balance)"""
    from sysai_framework.config.model_config import ModelConfigManager
    from sysai_framework.cli.constants import DEFAULT_CONFIG_PATH
    
    if not config_file:
        config_file = DEFAULT_CONFIG_PATH
    
    def online_mode(client):
        """Execute via D-Bus"""
        try:
            success, message = client.set_runtime_mode(mode)
            if success:
                Output.success(message)
                return 0
            else:
                Output.error(message)
                return 1
        except Exception as e:
            Output.error(f"Failed to set runtime mode: {e}")
            return 1
    
    def offline_mode():
        """Execute in offline mode"""
        try:
            config_manager = ModelConfigManager(config_path=config_file, allow_create_default=False)
            
            # Update runtime mode
            config_manager.routing_config.runtime.mode = mode
            
            # Persist to file
            config_manager.persist_routing_config()
            
            Output.success(f"Runtime mode set to: {mode}")
            return 0
            
        except Exception as e:
            Output.error(f"Failed to set runtime mode: {e}")
            logger.error(f"Offline mode failed: {e}", exc_info=True)
            return 1
    
    exit_code = auto_execute(
        online_func=online_mode,
        offline_func=offline_mode,
        operation_name="set runtime mode",
        require_config_file=True,
        config_path=config_file
    )
    
    sys.exit(exit_code)


@routing.command('set-strategy')
@click.option('--strategy', required=True,
              type=click.Choice(['round-robin', 'weighted', 'least-busy', 'lowest-latency', 'usage-based']),
              help='Load balance strategy')
@click.option('--config_path', 'config_file',
              help=f'Configuration file path (default: {DEFAULT_CONFIG_PATH})')
def routing_set_strategy(strategy: str, config_file: Optional[str]):
    """Set load balance strategy (only effective in load-balance mode)"""
    from sysai_framework.config.model_config import ModelConfigManager
    from sysai_framework.cli.constants import DEFAULT_CONFIG_PATH
    
    if not config_file:
        config_file = DEFAULT_CONFIG_PATH
    
    def online_mode(client):
        """Execute via D-Bus"""
        try:
            success, message = client.set_load_balance_strategy(strategy)
            if success:
                if "Note:" in message:
                    main_msg, note_msg = message.split("Note:", 1)
                    Output.success(main_msg.strip())
                    Output.warning(note_msg.strip())
                else:
                    Output.success(message)
                return 0
            else:
                Output.error(message)
                return 1
        except Exception as e:
            Output.error(f"Failed to set strategy: {e}")
            return 1
    
    def offline_mode():
        """Execute in offline mode"""
        try:
            config_manager = ModelConfigManager(config_path=config_file, allow_create_default=False)
            
            # Check if in load-balance mode
            if config_manager.routing_config.runtime.mode != "load-balance":
                Output.warning("Runtime mode is not 'load-balance'. Strategy setting will take effect when mode is changed.")
            
            # Update strategy
            config_manager.routing_config.runtime.load_balance.strategy = strategy
            
            # Persist to file
            config_manager.persist_routing_config()
            
            Output.success(f"Load balance strategy set to: {strategy}")
            return 0
            
        except Exception as e:
            Output.error(f"Failed to set strategy: {e}")
            logger.error(f"Offline mode failed: {e}", exc_info=True)
            return 1
    
    exit_code = auto_execute(
        online_func=online_mode,
        offline_func=offline_mode,
        operation_name="set load balance strategy",
        require_config_file=True,
        config_path=config_file
    )
    
    sys.exit(exit_code)


@routing.command('set-option')
@click.option('--key', required=True,
              type=click.Choice(['latency_buffer', 'latency_window', 'usage_window']),
              help='Option key to set')
@click.option('--value', required=True,
              help='Option value')
@click.option('--config_path', 'config_file',
              help=f'Configuration file path (default: {DEFAULT_CONFIG_PATH})')
def routing_set_option(key: str, value: str, config_file: Optional[str]):
    """Set load balance strategy option"""
    from sysai_framework.config.model_config import ModelConfigManager
    from sysai_framework.cli.constants import DEFAULT_CONFIG_PATH
    
    if not config_file:
        config_file = DEFAULT_CONFIG_PATH
    
    def online_mode(client):
        """Execute via D-Bus"""
        import json as json_module

        try:
            if key == 'latency_buffer':
                float_value = float(value)
                if not (0.0 <= float_value <= 1.0):
                    Output.error("latency_buffer must be between 0.0 and 1.0")
                    return 1
                options_dict = {key: float_value}
            elif key == 'latency_window':
                int_value = int(value)
                if int_value < 1:
                    Output.error("latency_window must be >= 1")
                    return 1
                options_dict = {key: int_value}
            elif key == 'usage_window':
                int_value = int(value)
                if int_value < 1:
                    Output.error("usage_window must be >= 1")
                    return 1
                options_dict = {key: int_value}

            success, message = client.update_load_balance_options(
                json_module.dumps(options_dict)
            )

            if success:
                if "Note:" in message:
                    main_msg, note_msg = message.split("Note:", 1)
                    Output.success(main_msg.strip())
                    Output.warning(note_msg.strip())
                else:
                    Output.success(f"Option '{key}' set to: {value}")
                return 0
            else:
                Output.error(message)
                return 1

        except ValueError as e:
            Output.error(f"Invalid value for {key}: {e}")
            return 1
        except Exception as e:
            Output.error(f"Failed to set option via D-Bus: {e}")
            return 1
    
    def offline_mode():
        """Execute in offline mode"""
        try:
            config_manager = ModelConfigManager(config_path=config_file, allow_create_default=False)
            options = config_manager.routing_config.runtime.load_balance.options
            
            # Parse and validate value
            if key == 'latency_buffer':
                float_value = float(value)
                if not (0.0 <= float_value <= 1.0):
                    Output.error("latency_buffer must be between 0.0 and 1.0")
                    return 1
                options.latency_buffer = float_value
            elif key == 'latency_window':
                int_value = int(value)
                if int_value < 1:
                    Output.error("latency_window must be >= 1")
                    return 1
                options.latency_window = int_value
            elif key == 'usage_window':
                int_value = int(value)
                if int_value < 1:
                    Output.error("usage_window must be >= 1")
                    return 1
                options.usage_window = int_value
            
            # Persist to file
            config_manager.persist_routing_config()
            
            Output.success(f"Option '{key}' set to: {value}")
            return 0
            
        except ValueError as e:
            Output.error(f"Invalid value for {key}: {e}")
            return 1
        except Exception as e:
            Output.error(f"Failed to set option: {e}")
            logger.error(f"Offline mode failed: {e}", exc_info=True)
            return 1
    
    exit_code = auto_execute(
        online_func=online_mode,
        offline_func=offline_mode,
        operation_name="set load balance option",
        require_config_file=True,
        config_path=config_file
    )
    
    sys.exit(exit_code)

