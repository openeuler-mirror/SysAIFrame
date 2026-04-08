"""
Copyright (C) 2025 CTyunOS. All Rights Reserved.
File: cli/utils/dbus_client.py
Desc: D-Bus client for CLI to communicate with SysAIFrame service
Date: 2025-11-27
Author: Liu Mingran
"""

import json
import logging
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger(__name__)

# D-Bus service constants
BUS_NAME = 'org.ctyunos.AIGateway.Chat'
ADMIN_OBJECT_PATH = '/org/ctyunos/AIGateway/Admin'
ADMIN_INTERFACE = 'org.ctyunos.AIGateway.Admin'

# Platform detection
try:
    import dbus
    DBUS_AVAILABLE = True
except ImportError:
    DBUS_AVAILABLE = False
    logger.debug("dbus-python not available")


class DBusClientError(Exception):
    """Base exception for D-Bus client errors"""
    pass


class ServiceNotRunningError(DBusClientError):
    """Raised when the SysAIFrame service is not running"""
    pass


class DBusNotAvailableError(DBusClientError):
    """Raised when D-Bus is not available on the system"""
    pass


class AdminDBusClient:
    """
    D-Bus client for model configuration admin operations.

    Usage:
        client = AdminDBusClient()
        if client.is_service_running():
            success, message, instance_id = client.add_model(model_data)
    """

    def __init__(self, use_system_bus: bool = True):
        """
        Initialize D-Bus client.

        Args:
            use_system_bus: Use system bus (True) or session bus (False)
        """
        self.use_system_bus = use_system_bus
        self._bus = None
        self._admin_interface = None

    def _get_bus(self):
        """Get D-Bus connection"""
        if not DBUS_AVAILABLE:
            raise DBusNotAvailableError(
                "D-Bus is not available. Please install dbus-python."
            )

        if self._bus is None:
            try:
                if self.use_system_bus:
                    try:
                        self._bus = dbus.SystemBus()
                    except Exception:
                        # Fallback to session bus
                        self._bus = dbus.SessionBus()
                else:
                    self._bus = dbus.SessionBus()
            except AttributeError as e:
                # D-Bus module exists but functionality not available (e.g., macOS)
                raise DBusNotAvailableError(
                    f"D-Bus functionality is not available on this system: {e}"
                )

        return self._bus

    def _get_admin_interface(self):
        """Get Admin D-Bus interface"""
        if self._admin_interface is None:
            bus = self._get_bus()
            try:
                proxy = bus.get_object(BUS_NAME, ADMIN_OBJECT_PATH)
                self._admin_interface = dbus.Interface(proxy, ADMIN_INTERFACE)
            except dbus.exceptions.DBusException as e:
                if 'org.freedesktop.DBus.Error.ServiceUnknown' in str(e):
                    raise ServiceNotRunningError(
                        "SysAIFrame service is not running. "
                        "Please start the service first: sudo systemctl start sysaiframe"
                    )
                else:
                    raise DBusClientError(f"D-Bus error: {e}")

        return self._admin_interface

    def is_service_running(self) -> bool:
        """Check if the SysAIFrame service is running"""
        try:
            interface = self._get_admin_interface()
            status = interface.GetStatus()
            return status.get('status') == 'running'
        except ServiceNotRunningError:
            return False
        except Exception:
            return False

    def add_model(
        self,
        model_data: Dict[str, Any],
        force: bool = False,
        set_as_default: bool = False
    ) -> 'OperationResult':
        """
        Add a new model configuration.

        Args:
            model_data: Model configuration dictionary
            force: Force overwrite if instance_id exists
            set_as_default: Set this model as the default model

        Returns:
            OperationResult with status, message, and instance_id as data

        Raises:
            ServiceNotRunningError: If service is not running
            DBusClientError: If D-Bus call fails
        """
        from sysai_framework.core.status_codes import (
            OperationResult, parse_status_from_message, SUCCESS, INTERNAL_ERROR
        )

        admin = self._get_admin_interface()

        try:
            model_data_json = json.dumps(model_data, ensure_ascii=False)
            success, message, instance_id = admin.AddModel(model_data_json, force, set_as_default)

            # Parse status code from message if present
            status, pure_message = parse_status_from_message(str(message))

            if success:
                return OperationResult(
                    status=status or SUCCESS,
                    data=str(instance_id),
                    details={
                        "instance_id": str(instance_id),
                        "_formatted_message": pure_message
                    }
                )
            else:
                return OperationResult(
                    status=status or INTERNAL_ERROR,
                    details={
                        "instance_id": str(instance_id),
                        "_formatted_message": pure_message
                    }
                )
        except dbus.exceptions.DBusException as e:
            raise DBusClientError(f"Failed to add model: {e}")

    def list_models(self) -> List[Dict[str, Any]]:
        """
        List all configured models.

        Returns:
            List of model configurations

        Raises:
            ServiceNotRunningError: If service is not running
            DBusClientError: If D-Bus call fails
        """
        admin = self._get_admin_interface()

        try:
            models_json = admin.ListModels()
            if models_json:
                return json.loads(models_json)
            return []
        except dbus.exceptions.DBusException as e:
            raise DBusClientError(f"Failed to list models: {e}")
