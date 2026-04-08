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


