"""
Copyright (C) 2025 CTyunOS. All Rights Reserved.
File: admin_methods.py
Desc: D-Bus admin methods for model configuration management
Date: 2025-11-27
Author: Liu Mingran
"""

import logging
import json
from typing import Dict, Any, Tuple

logger = logging.getLogger(__name__)

# Platform detection
try:
    import dbus
    import dbus.service
    DBUS_AVAILABLE = True
except ImportError:
    DBUS_AVAILABLE = False
    dbus = None
    logger.warning("dbus-python not available")


# Base class depending on D-Bus availability
if DBUS_AVAILABLE:
    _BaseClass = dbus.service.Object
else:
    _BaseClass = object


def _dbus_method(interface, in_sig, out_sig):
    """Decorator factory that wraps dbus.service.method or returns identity"""
    if DBUS_AVAILABLE:
        return dbus.service.method(interface, in_signature=in_sig, out_signature=out_sig)
    else:
        def identity(func):
            return func
        return identity


class AdminServiceObject(_BaseClass):
    """
    D-Bus service object implementing model configuration admin methods.
    """

    INTERFACE_NAME = 'org.ctyunos.AIGateway.Admin'

    def __init__(self, bus_name, object_path):
        """
        Initialize admin service object.

        Args:
            bus_name: D-Bus bus name
            object_path: D-Bus object path
        """
        if DBUS_AVAILABLE:
            super().__init__(bus_name, object_path)

        # Import config manager
        try:
            from sysai_framework.config import get_config_manager
            self.config_manager = get_config_manager()
            logger.info("Admin service object initialized with config manager")
        except Exception as e:
            logger.error(f"Failed to initialize config manager: {e}", exc_info=True)
            self.config_manager = None

    def _model_config_to_dict(self, model_config) -> Dict[str, Any]:
        """Convert ModelConfig to dictionary (hide sensitive data)"""
        return {
            'name': model_config.name,
            'instance_id': model_config.instance_id,
            'provider': model_config.provider,
            'api_base': model_config.api_base,
            'api_key': '***' if model_config.api_key else None,
            'priority': model_config.priority,
            'capabilities': model_config.capabilities,
            'supports_streaming': model_config.supports_streaming,
            'timeout': model_config.timeout,
            'max_retries': model_config.max_retries,
            'is_healthy': model_config.is_healthy,
        }

    @_dbus_method(INTERFACE_NAME, 'sbb', 'bss')
    def AddModel(self, model_data_json: str, force: bool, set_as_default: bool) -> Tuple[bool, str, str]:
        """
        Add a new model configuration.

        Args:
            model_data_json: Model configuration as JSON string
            force: Force overwrite if instance_id exists
            set_as_default: Set this model as the default model

        Returns:
            (success, message, instance_id)
            Message format: "[STATUS:code] message" for new status code system
        """
        from sysai_framework.core.status_codes import encode_status_in_message, VALIDATION_ERROR

        logger.info(f"D-Bus AddModel called, force={force}, set_as_default={set_as_default}")

        if not self.config_manager:
            error_msg = encode_status_in_message(VALIDATION_ERROR, "Config manager not available")
            return (False, error_msg, "")

        try:
            # Parse JSON
            model_data = json.loads(model_data_json)

            api_base = model_data.get('api_base') or model_data.get('endpoint')
            if api_base and not (api_base.startswith('http://') or api_base.startswith('https://')):
                error_msg = encode_status_in_message(VALIDATION_ERROR, "Invalid API base URL: must start with http:// or https://")
                return (False, error_msg, "")

            # Call config manager to add model (now returns OperationResult)
            result = self.config_manager.add_model(
                model_data,
                persist=True,
                force=force,
                require_file_lock=False,  # Service process: use thread lock only
                set_as_default=set_as_default
            )

            instance_id = result.data.instance_id if result.data else ""

            # Encode status code in message for backward compatibility
            message = encode_status_in_message(result.status, result.get_message())

            if result.success:
                logger.info(f"Model added via D-Bus: {model_data.get('name')} (instance_id={instance_id})")
            else:
                logger.warning(f"Failed to add model via D-Bus: {message}")

            return (result.success, message, instance_id)

        except json.JSONDecodeError as e:
            error_msg = encode_status_in_message(VALIDATION_ERROR, f"Invalid JSON: {e}")
            logger.error(error_msg)
            return (False, error_msg, "")
        except Exception as e:
            from sysai_framework.core.status_codes import INTERNAL_ERROR
            error_msg = encode_status_in_message(INTERNAL_ERROR, f"Failed to add model: {e}")
            logger.error(error_msg, exc_info=True)
            return (False, error_msg, "")

    @_dbus_method(INTERFACE_NAME, '', 's')
    def ListModels(self) -> str:
        """
        List all configured models.

        Returns:
            JSON string containing array of model configurations
        """
        logger.debug("D-Bus ListModels called")

        if not self.config_manager:
            return json.dumps([])

        try:
            models_list = []
            for model_config in self.config_manager.models.values():
                models_list.append(self._model_config_to_dict(model_config))

            return json.dumps(models_list, ensure_ascii=False)

        except Exception as e:
            logger.error(f"Failed to list models: {e}", exc_info=True)
            return json.dumps([])

    @_dbus_method(INTERFACE_NAME, 's', 's')
    def GetModel(self, identifier: str) -> str:
        """
        Get model configuration by identifier.

        Args:
            identifier: Model name or instance_id

        Returns:
            JSON string containing model configuration(s), empty if not found
        """
        logger.debug(f"D-Bus GetModel called: {identifier}")

        if not self.config_manager:
            return "[]"

        try:
            matching = []

            # Try to get by model name (may return multiple instances)
            models_by_name = self.config_manager.get_models_by_name(identifier)
            if models_by_name:
                for model_config in models_by_name:
                    matching.append(self._model_config_to_dict(model_config))

            # If not found by name, try instance_id
            if not matching:
                model_config = self.config_manager.get_model_by_instance_id(identifier)
                if model_config:
                    matching.append(self._model_config_to_dict(model_config))

            if not matching:
                return "[]"

            # Return single object if only one match, otherwise array
            if len(matching) == 1:
                return json.dumps(matching[0], ensure_ascii=False)
            else:
                return json.dumps(matching, ensure_ascii=False)

        except Exception as e:
            logger.error(f"Failed to get model: {e}", exc_info=True)
            return "[]"

    @_dbus_method(INTERFACE_NAME, 's', 'bs')
    def RemoveModel(self, instance_id: str) -> Tuple[bool, str]:
        """
        Remove a model by instance_id.

        Args:
            instance_id: Instance ID of the model to remove

        Returns:
            (success, message)
            Message format: "[STATUS:code] message" for new status code system
        """
        from sysai_framework.core.status_codes import (
            encode_status_in_message, MODEL_NOT_FOUND, DELETED,
            VALIDATION_ERROR, INTERNAL_ERROR
        )

        logger.info(f"D-Bus RemoveModel called: {instance_id}")

        if not self.config_manager:
            error_msg = encode_status_in_message(VALIDATION_ERROR, "Config manager not available")
            return (False, error_msg)

        try:
            # Check if model exists
            if instance_id not in self.config_manager.models:
                error_msg = encode_status_in_message(
                    MODEL_NOT_FOUND,
                    MODEL_NOT_FOUND.message_template.format(model=instance_id)
                )
                return (False, error_msg)

            # Remove from memory (returns True if it was the default model)
            is_default = self.config_manager._remove_model_from_memory(instance_id)

            # Remove from file
            self._remove_model_from_file(instance_id)

            # Clear default model in file if needed
            if is_default:
                self.config_manager._clear_default_model_in_file()
                logger.info(f"Cleared default model settings after removing {instance_id}")

            logger.info(f"Model removed via D-Bus: instance_id={instance_id}")
            success_msg = encode_status_in_message(DELETED, "Model removed successfully")
            return (True, success_msg)

        except Exception as e:
            error_msg = encode_status_in_message(INTERNAL_ERROR, f"Failed to remove model: {e}")
            logger.error(error_msg, exc_info=True)
            return (False, error_msg)

    def _remove_model_from_file(self, instance_id: str) -> None:
        """Remove model from configuration file"""
        import os
        from ruamel.yaml import YAML

        config_path = self.config_manager.config_path
        if not os.path.exists(config_path):
            return

        yaml_obj = YAML()
        yaml_obj.preserve_quotes = True

        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml_obj.load(f)

        if config and 'models' in config:
            # Find and remove model by instance_id
            models = config['models']
            for i in range(len(models) - 1, -1, -1):
                if models[i].get('instance_id') == instance_id:
                    del models[i]
                    break

            # Write back
            with open(config_path, 'w', encoding='utf-8') as f:
                yaml_obj.dump(config, f)

    @_dbus_method(INTERFACE_NAME, '', 'bs')
    def ReloadConfig(self) -> Tuple[bool, str]:
        """
        Reload configuration from file.

        Returns:
            (success, message)
            Message format: "[STATUS:code] message" for new status code system
        """
        from sysai_framework.core.status_codes import (
            encode_status_in_message, CONFIG_RELOADED,
            CONFIG_INVALID, VALIDATION_ERROR, INTERNAL_ERROR
        )

        logger.info("D-Bus ReloadConfig called")

        if not self.config_manager:
            error_msg = encode_status_in_message(VALIDATION_ERROR, "Config manager not available")
            return (False, error_msg)

        try:
            success = self.config_manager.reload_config()

            if success:
                logger.info("Configuration reloaded via D-Bus")
                success_msg = encode_status_in_message(CONFIG_RELOADED, "Configuration reloaded successfully")
                return (True, success_msg)
            else:
                error_msg = encode_status_in_message(CONFIG_INVALID, "Failed to reload configuration")
                return (False, error_msg)

        except Exception as e:
            error_msg = encode_status_in_message(INTERNAL_ERROR, f"Failed to reload configuration: {e}")
            logger.error(error_msg, exc_info=True)
            return (False, error_msg)

    @_dbus_method(INTERFACE_NAME, '', 's')
    def GetServiceConfigPath(self) -> str:
        """
        Get the configuration file path currently used by the service.

        Returns:
            Configuration file path as string
        """
        logger.debug("D-Bus GetServiceConfigPath called")

        if not self.config_manager:
            return ""

        try:
            return self.config_manager.config_path
        except Exception as e:
            logger.error(f"Failed to get service config path: {e}", exc_info=True)
            return ""

    @_dbus_method(INTERFACE_NAME, '', 's')
    def GetRoutingConfig(self) -> str:
        """
        Get current routing configuration including default model.

        Returns:
            JSON string containing routing configuration
        """
        logger.debug("D-Bus GetRoutingConfig called")

        try:
            if not self.config_manager:
                return json.dumps({
                    "default_model": None,
                    "default_model_instance_id": None
                })

            result = {
                "default_model": self.config_manager.default_model,
                "default_model_instance_id": self.config_manager.default_model_instance_id
            }

            return json.dumps(result, ensure_ascii=False)

        except Exception as e:
            logger.error(f"Failed to get routing config: {e}", exc_info=True)
            return json.dumps({
                "default_model": None,
                "default_model_instance_id": None
            })

    @_dbus_method(INTERFACE_NAME, 'ss', 'bs')
    def SetDefaultModel(self, model_name: str, instance_id: str) -> Tuple[bool, str]:
        """
        Set default model for routing.

        Args:
            model_name: Model name to set as default
            instance_id: Optional specific instance ID (empty string if not specified)

        Returns:
            (success, message)
            Message format: "[STATUS:code] message" for new status code system
        """
        from sysai_framework.core.status_codes import (
            encode_status_in_message, SUCCESS,
            MODEL_NOT_FOUND, VALIDATION_ERROR, INTERNAL_ERROR
        )

        logger.info(f"D-Bus SetDefaultModel called: model_name={model_name}, instance_id={instance_id}")

        if not self.config_manager:
            error_msg = encode_status_in_message(VALIDATION_ERROR, "Config manager not available")
            return (False, error_msg)

        try:
            # Convert empty string to None
            instance_id_value = instance_id if instance_id else None

            # Call config manager to set default model
            result = self.config_manager.set_default_model(
                model_name=model_name,
                instance_id=instance_id_value,
                persist=True,
                require_file_lock=False  # D-Bus call, already in service process
            )

            if result.success:
                logger.info(
                    f"Default model set via D-Bus: model_name={model_name}, "
                    f"instance_id={instance_id_value}"
                )
                success_msg = encode_status_in_message(SUCCESS, result.get_message())
                return (True, success_msg)
            else:
                # Map error codes - use the status code from result, or INTERNAL_ERROR as fallback
                status_code = result.status if result.status != SUCCESS else INTERNAL_ERROR
                error_msg = encode_status_in_message(status_code, result.get_message())
                return (False, error_msg)

        except Exception as e:
            error_msg = encode_status_in_message(INTERNAL_ERROR, f"Failed to set default model: {e}")
            logger.error(error_msg, exc_info=True)
            return (False, error_msg)

    @_dbus_method(INTERFACE_NAME, '', 's')
    def GetServiceStatus(self) -> str:
        """
        Get current service operational status.

        Returns:
            JSON string containing service status information
        """
        logger.debug("D-Bus GetServiceStatus called")

        try:
            from sysai_framework.core.service_status import get_service_status, update_service_status
            from sysai_framework.config import get_config_manager

            # Update status from current configuration
            config_manager = get_config_manager()
            update_service_status(config_manager)

            # Get status
            service_status = get_service_status()
            status_info = service_status.to_dict()

            # Convert to expected format for D-Bus
            # status_info["state"] is already a string (e.g., "ready", "degraded", "error")
            state_value = status_info["state"].upper()
            result = {
                "state": state_value,
                "message": status_info.get("error_message") or f"Service is {status_info['state']}",
                "model_count": status_info["total_models"],
                "healthy_model_count": status_info["healthy_models"],
                "config_status": {
                    "last_load_success": True,
                    "last_load_message": "Configuration loaded successfully"
                }
            }

            return json.dumps(result, ensure_ascii=False)

        except Exception as e:
            logger.error(f"Failed to get service status: {e}", exc_info=True)
            # Return minimal error status
            return json.dumps({
                "state": "ERROR",
                "message": f"Failed to get status: {str(e)}",
                "model_count": 0,
                "healthy_model_count": 0,
                "config_status": {
                    "last_load_success": False,
                    "last_load_message": "Error retrieving status"
                }
            })

    @_dbus_method(INTERFACE_NAME, 's', 's')
    def GetHealthStatus(self, model_name: str) -> str:
        """
        Get health status for specified model or all models.

        Args:
            model_name: Model name (empty string for all models)

        Returns:
            JSON string containing health status information
        """
        logger.debug(f"D-Bus GetHealthStatus called for model: {model_name or 'all'}")

        try:
            from sysai_framework.router import get_router

            router = get_router()
            stats = router.get_health_statistics()

            if model_name:
                # Filter for specific model
                model_instances = [
                    m for m in stats.get("models", [])
                    if m.get("name") == model_name
                ]

                if not model_instances:
                    return json.dumps({
                        "error": f"Model '{model_name}' not found",
                        "available_models": list(set(m.get("name") for m in stats.get("models", [])))
                    }, ensure_ascii=False)

                result = {
                    "model_name": model_name,
                    "total_instances": len(model_instances),
                    "healthy_instances": sum(1 for m in model_instances if m.get("is_healthy")),
                    "instances": model_instances
                }
            else:
                # Return all models
                result = stats

            return json.dumps(result, ensure_ascii=False)

        except Exception as e:
            logger.error(f"Failed to get health status: {e}", exc_info=True)
            return json.dumps({"error": f"Failed to get health status: {str(e)}"}, ensure_ascii=False)

    @_dbus_method(INTERFACE_NAME, 's', 'bs')
    def TriggerHealthCheck(self, model_name: str) -> Tuple[bool, str]:
        """
        Manually trigger health check for specified model or all models.

        Args:
            model_name: Model name (empty string for all models)

        Returns:
            Tuple of (success, message)
        """
        logger.debug(f"D-Bus TriggerHealthCheck called for model: {model_name or 'all'}")

        try:
            from sysai_framework.router import get_router

            router = get_router()

            if model_name:
                # Check specific model
                model_config = self.config_manager.get_model_config(model_name)
                if not model_config:
                    return (False, f"Model '{model_name}' not found")

                router.trigger_health_check(model_name)
                return (True, f"Health check triggered for model '{model_name}'")
            else:
                # Check all models
                router.trigger_health_check()
                return (True, "Health check triggered for all models")

        except Exception as e:
            logger.error(f"Failed to trigger health check: {e}", exc_info=True)
            return (False, f"Failed to trigger health check: {str(e)}")

    @_dbus_method(INTERFACE_NAME, '', 's')
    def GetHealthCheckConfig(self) -> str:
        """
        Get current health check configuration.

        Returns:
            JSON string containing health check configuration
        """
        logger.debug("D-Bus GetHealthCheckConfig called")

        # Check if config_manager is available
        if not self.config_manager:
            error_msg = json.dumps({
                "error": "Config manager not available. Service may be shutting down."
            }, ensure_ascii=False)
            logger.error("GetHealthCheckConfig failed: config_manager is None")
            return error_msg

        try:
            routing_config = self.config_manager.routing_config
            health_config = routing_config.health_check

            result = {
                "lightweight_enabled": health_config.lightweight_enabled,
                "lightweight_interval": health_config.lightweight_interval,
                "actual_request_enabled": health_config.actual_request_enabled,
                "actual_request_interval": health_config.actual_request_interval,
                "timeout": health_config.timeout
            }

            return json.dumps(result, ensure_ascii=False)

        except Exception as e:
            logger.error(f"Failed to get health check config: {e}", exc_info=True)
            return json.dumps({"error": f"Failed to get health check config: {str(e)}"}, ensure_ascii=False)

    @_dbus_method(INTERFACE_NAME, 's', 'bs')
    def UpdateHealthCheckConfig(self, config_json: str) -> Tuple[bool, str]:
        """
        Update health check configuration (hot reload).

        Args:
            config_json: JSON string containing health check configuration

        Returns:
            Tuple of (success, message)
        """
        logger.debug(f"D-Bus UpdateHealthCheckConfig called with: {config_json}")

        # Check if config_manager is available
        if not self.config_manager:
            logger.error("UpdateHealthCheckConfig failed: config_manager is None")
            return (False, "Config manager not available. Service may be shutting down.")

        try:
            config_dict = json.loads(config_json)

            # Validate configuration keys
            valid_keys = {
                "lightweight_enabled", "lightweight_interval",
                "actual_request_enabled", "actual_request_interval", "timeout"
            }
            invalid_keys = set(config_dict.keys()) - valid_keys
            if invalid_keys:
                return (False, f"Invalid configuration keys: {', '.join(invalid_keys)}")

            # Define reasonable value ranges
            value_limits = {
                "lightweight_interval": (1, 3600),  # 1 second to 1 hour
                "actual_request_interval": (60, 86400),  # 1 minute to 1 day
                "timeout": (1, 300),  # 1 second to 5 minutes
            }

            # Validate numeric values with range checks
            for key in ["lightweight_interval", "actual_request_interval", "timeout"]:
                if key in config_dict:
                    value = config_dict[key]
                    if not isinstance(value, int):
                        return (False, f"'{key}' must be an integer")

                    min_val, max_val = value_limits[key]
                    if not (min_val <= value <= max_val):
                        return (False, f"'{key}' must be between {min_val} and {max_val} seconds")

            # Update configuration in config_manager
            routing_config = self.config_manager.routing_config
            health_config = routing_config.health_check

            # Apply updates
            for key, value in config_dict.items():
                setattr(health_config, key, value)

            # Persist to file
            try:
                self.config_manager.persist_routing_config()
                logger.info(f"Health check configuration persisted to file: {config_dict}")
            except Exception as persist_error:
                logger.error(f"Failed to persist configuration: {persist_error}")
                # Continue anyway, configuration is applied in-memory

            # Notify router's health checker of config update
            from sysai_framework.router import get_router
            router = get_router()
            router.health_checker.update_config(config_dict)

            return (True, "Health check configuration updated successfully")

        except json.JSONDecodeError as e:
            return (False, f"Invalid JSON: {str(e)}")
        except Exception as e:
            logger.error(f"Failed to update health check config: {e}", exc_info=True)
            return (False, f"Failed to update health check config: {str(e)}")

    @_dbus_method(INTERFACE_NAME, '', 's')
    def GetRetryPolicyConfig(self) -> str:
        """
        Get current retry policy configuration.

        Returns:
            JSON string containing retry policy configuration
        """
        logger.debug("D-Bus GetRetryPolicyConfig called")

        # Check if config_manager is available
        if not self.config_manager:
            error_msg = json.dumps({
                "error": "Config manager not available. Service may be shutting down."
            }, ensure_ascii=False)
            logger.error("GetRetryPolicyConfig failed: config_manager is None")
            return error_msg

        try:
            routing_config = self.config_manager.routing_config
            retry_policy = routing_config.retry_policy

            result = {
                "max_attempts": retry_policy.max_attempts,
                "backoff_factor": retry_policy.backoff_factor,
                "base_delay": retry_policy.base_delay,
                "max_delay": retry_policy.max_delay
            }

            return json.dumps(result, ensure_ascii=False)

        except Exception as e:
            logger.error(f"Failed to get retry policy config: {e}", exc_info=True)
            return json.dumps({"error": f"Failed to get retry policy config: {str(e)}"}, ensure_ascii=False)


