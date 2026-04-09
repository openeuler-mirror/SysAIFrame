"""
SysAI Client - Main client for interacting with SysAIFrame

Copyright (C) 2025 CTyunOS. All Rights Reserved.
"""

import logging
from typing import List, Optional, Dict, Any, Union, Iterator

logger = logging.getLogger(__name__)

try:
    import dbus
    from dbus.mainloop.glib import DBusGMainLoop
    DBUS_AVAILABLE = True
except ImportError:
    DBUS_AVAILABLE = False
    logger.warning("D-Bus dependencies not available")

from .types import (
    ChatMessage,
    ChatResponse,
    ChatChunk,
    SysAIConnectionError,
    ServiceUnavailableError,
    InvalidRequestError,
    ServerError,
    ModelNotFoundError,
    SysAITimeoutError,
)
from .streaming import StreamIterator


class SysAIClient:
    """
    Client for SysAIFrame AI Gateway.

    Provides methods for chat completion (streaming and non-streaming),
    model listing, and service status.
    """

    BUS_NAME = "org.ctyunos.AIGateway.Chat"
    OBJECT_PATH = "/org/ctyunos/AIGateway/Chat"
    INTERFACE_NAME = "org.ctyunos.AIGateway.Chat"

    def __init__(self, use_system_bus: bool = True):
        """
        Initialize SysAI client.

        Args:
            use_system_bus: Use system bus (True) or session bus (False)

        Raises:
            SysAIConnectionError: If D-Bus connection fails
        """
        if not DBUS_AVAILABLE:
            raise SysAIConnectionError("D-Bus dependencies not available. Install dbus-python and PyGObject.")

        self.use_system_bus = use_system_bus
        self.bus: Optional[dbus.Bus] = None
        self.interface: Optional[dbus.Interface] = None

        self._connect()

    def _connect(self):
        """Connect to D-Bus and get interface"""
        try:
            DBusGMainLoop(set_as_default=True)

            if self.use_system_bus:
                try:
                    self.bus = dbus.SystemBus()
                    logger.debug("Connected to system D-Bus")
                except Exception as e:
                    logger.warning(f"Failed to connect to system bus: {e}, trying session bus")
                    self.bus = dbus.SessionBus()
                    logger.debug("Connected to session D-Bus")
            else:
                self.bus = dbus.SessionBus()
                logger.debug("Connected to session D-Bus")

            proxy = self.bus.get_object(self.BUS_NAME, self.OBJECT_PATH)
            self.interface = dbus.Interface(proxy, self.INTERFACE_NAME)

            logger.info(f"SysAI client connected to {self.BUS_NAME}")

        except dbus.DBusException as e:
            raise SysAIConnectionError(f"Failed to connect to D-Bus: {e}")
        except Exception as e:
            raise SysAIConnectionError(f"Unexpected error connecting to D-Bus: {e}")

    def _python_to_dbus(self, value: Any) -> Any:
        """Convert Python value to D-Bus type"""
        if value is None:
            return dbus.String("")
        elif isinstance(value, bool):
            return dbus.Boolean(value)
        elif isinstance(value, int):
            return dbus.Int64(value)
        elif isinstance(value, float):
            return dbus.Double(value)
        elif isinstance(value, str):
            return dbus.String(value)
        elif isinstance(value, list):
            if not value:
                return dbus.Array([], signature='v')
            converted = [self._python_to_dbus(item) for item in value]
            return dbus.Array(converted, signature='v')
        elif isinstance(value, dict):
            converted = {}
            for k, v in value.items():
                converted[str(k)] = self._python_to_dbus(v)
            return dbus.Dictionary(converted, signature='sv')
        else:
            return dbus.String(str(value))

    def _dbus_to_python(self, value: Any) -> Any:
        """Convert D-Bus value to Python type"""
        if isinstance(value, dbus.Dictionary):
            return {self._dbus_to_python(k): self._dbus_to_python(v) for k, v in value.items()}
        elif isinstance(value, dbus.Array):
            return [self._dbus_to_python(item) for item in value]
        elif isinstance(value, dbus.Boolean):
            return bool(value)
        elif isinstance(value, (dbus.Int16, dbus.Int32, dbus.Int64,
                               dbus.UInt16, dbus.UInt32, dbus.UInt64)):
            return int(value)
        elif isinstance(value, dbus.Double):
            return float(value)
        elif isinstance(value, (dbus.String, dbus.ObjectPath, dbus.Signature)):
            s = str(value)
            return None if s == "" else s
        elif isinstance(value, dbus.Byte):
            return int(value)
        return value
