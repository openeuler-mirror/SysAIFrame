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
