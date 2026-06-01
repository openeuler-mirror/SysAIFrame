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
            # Initialize GLib main loop integration
            DBusGMainLoop(set_as_default=True)

            # Connect to bus
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

            # Get proxy object
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
            # D-Bus doesn't have null, use empty string
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
            # Empty string represents null
            return None if s == "" else s
        elif isinstance(value, dbus.Byte):
            return int(value)
        return value

    def _build_request(
        self,
        messages: List[Union[Dict[str, str], ChatMessage]],
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        top_p: Optional[float] = None,
        stream: bool = False,
    ) -> Dict[str, Any]:
        """Build request dictionary for D-Bus call"""
        request = {}

        # Convert messages
        msg_list = []
        for msg in messages:
            if isinstance(msg, ChatMessage):
                msg_list.append(msg.to_dict())
            elif isinstance(msg, dict):
                msg_list.append(msg)
            else:
                raise InvalidRequestError(f"Invalid message type: {type(msg)}")

        request["messages"] = msg_list
        request["stream"] = stream

        # Add optional parameters
        if model is not None:
            request["model"] = model
        if temperature is not None:
            request["temperature"] = temperature
        if max_tokens is not None:
            request["max_tokens"] = max_tokens
        if top_p is not None:
            request["top_p"] = top_p

        return request

    def _handle_api_error(self, error: Dict[str, Any]) -> Exception:
        """Map API error dictionary to SDK Exception"""
        error_msg = error.get("message", "Unknown error")
        error_type = error.get("type", "unknown").lower()

        # 1. Map by explicit type
        if "not_found" in error_type:
            return ModelNotFoundError(error_msg)
        elif "unavailable" in error_type:
            return ServiceUnavailableError(error_msg)
        elif "invalid" in error_type or "validation" in error_type:
            return InvalidRequestError(error_msg)

        # 2. Map by status code prefix
        if "[STATUS:404]" in error_msg:
            return ModelNotFoundError(error_msg)
        elif "[STATUS:400]" in error_msg:
            return InvalidRequestError(error_msg)
        elif "[STATUS:503]" in error_msg:
            return ServiceUnavailableError(error_msg)

        # 3. Handle specific timeout
        if "timeout" in error_msg.lower():
            return SysAITimeoutError(error_msg)

        # 4. Fallback to generic string matching
        msg_lower = error_msg.lower()
        if "not found" in msg_lower:
            return ModelNotFoundError(error_msg)
        elif "unavailable" in msg_lower:
            return ServiceUnavailableError(error_msg)
        elif "invalid" in msg_lower:
            return InvalidRequestError(error_msg)

        return ServerError(error_msg)

    def _handle_dbus_error(self, e: Exception) -> Exception:
        """Map dbus.DBusException to SDK Exception"""
        if not hasattr(e, "get_dbus_name"):
            return ServerError(f"D-Bus error: {e}")
        error_name = e.get_dbus_name()
        if "ServiceUnknown" in error_name or "NameHasNoOwner" in error_name:
            return ServiceUnavailableError(f"SysAIFrame service not available: {e}")
        elif "NoReply" in error_name or "Timeout" in error_name:
            return SysAITimeoutError(f"Request timeout: {e}")
        return ServerError(f"D-Bus error: {e}")

    def chat(
        self,
        messages: List[Union[Dict[str, str], ChatMessage]],
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        top_p: Optional[float] = None,
    ) -> ChatResponse:
        """
        Send a chat completion request (non-streaming).

        Args:
            messages: List of messages (dict or ChatMessage objects)
            model: Model name (optional, uses system default if not specified)
            temperature: Sampling temperature (0.0 to 2.0)
            max_tokens: Maximum tokens to generate
            top_p: Nucleus sampling parameter

        Returns:
            ChatResponse object

        Raises:
            SysAIConnectionError: If D-Bus connection fails
            ServiceUnavailableError: If service is not available
            InvalidRequestError: If request parameters are invalid
            ModelNotFoundError: If specified model is not found
            ServerError: If server returns an error
        """
        if not self.interface:
            raise SysAIConnectionError("Not connected to D-Bus")

        try:
            # Build request
            request = self._build_request(
                messages=messages,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                top_p=top_p,
                stream=False
            )

            # Convert to D-Bus types
            dbus_request = self._python_to_dbus(request)

            logger.debug(f"Sending chat request: model={model}")

            # Call D-Bus method
            dbus_response = self.interface.ChatCompletion(dbus_request)

            # Convert response
            response = self._dbus_to_python(dbus_response)

            # Check for errors
            if "error" in response:
                raise self._handle_api_error(response["error"])

            return ChatResponse.from_dict(response)

        except dbus.DBusException as e:
            raise self._handle_dbus_error(e)
        except (SysAIConnectionError, ServiceUnavailableError, InvalidRequestError,
                ModelNotFoundError, ServerError, SysAITimeoutError):
            raise
        except Exception as e:
            raise ServerError(f"Unexpected error: {e}")

    def chat_stream(
        self,
        messages: List[Union[Dict[str, str], ChatMessage]],
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        top_p: Optional[float] = None,
        timeout: int = 120,
    ) -> Iterator[ChatChunk]:
        """
        Send a chat completion request with streaming.

        Args:
            messages: List of messages (dict or ChatMessage objects)
            model: Model name (optional, uses system default if not specified)
            temperature: Sampling temperature (0.0 to 2.0)
            max_tokens: Maximum tokens to generate
            top_p: Nucleus sampling parameter
            timeout: Timeout in seconds for receiving chunks

        Returns:
            Iterator of ChatChunk objects

        Raises:
            SysAIConnectionError: If D-Bus connection fails
            ServiceUnavailableError: If service is not available
            InvalidRequestError: If request parameters are invalid
            ModelNotFoundError: If specified model is not found
            ServerError: If server returns an error
        """
        if not self.interface:
            raise SysAIConnectionError("Not connected to D-Bus")

        try:
            # Build request
            request = self._build_request(
                messages=messages,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                top_p=top_p,
                stream=True
            )

            # Convert to D-Bus types
            dbus_request = self._python_to_dbus(request)

            logger.debug(f"Sending streaming chat request: model={model}")

            # Call D-Bus method to get initial response
            dbus_response = self.interface.ChatCompletion(dbus_request)
            response = self._dbus_to_python(dbus_response)

            # Check for errors
            if "error" in response:
                raise self._handle_api_error(response["error"])

            # Extract request_id and model from initial response
            request_id = response.get("id")
            actual_model = response.get("model", model or "default")

            if not request_id:
                raise ServerError("No request_id in streaming response")

            logger.debug(f"Got streaming request_id: {request_id}")

            # Create stream iterator
            stream_iter = StreamIterator(self.bus, request_id, actual_model, timeout)
            stream_iter.start()

            return stream_iter

        except dbus.DBusException as e:
            raise self._handle_dbus_error(e)
        except (SysAIConnectionError, ServiceUnavailableError, InvalidRequestError,
                ModelNotFoundError, ServerError, SysAITimeoutError):
            raise
        except Exception as e:
            raise ServerError(f"Unexpected error: {e}")

    def list_models(self) -> List[str]:
        """
        Get list of available models.

        Returns:
            List of model names

        Raises:
            SysAIConnectionError: If D-Bus connection fails
            ServiceUnavailableError: If service is not available
            ServerError: If server returns an error
        """
        if not self.interface:
            raise SysAIConnectionError("Not connected to D-Bus")

        try:
            models = self.interface.GetChatModels()
            return [str(m) for m in models]
        except dbus.DBusException as e:
            raise self._handle_dbus_error(e)
        except Exception as e:
            raise ServerError(f"Unexpected error: {e}")

    def get_status(self) -> Dict[str, Any]:
        """
        Get service status.

        Returns:
            Status dictionary

        Raises:
            SysAIConnectionError: If D-Bus connection fails
            ServiceUnavailableError: If service is not available
            ServerError: If server returns an error
        """
        if not self.interface:
            raise SysAIConnectionError("Not connected to D-Bus")

        try:
            dbus_status = self.interface.GetStatus()
            status_str = self._dbus_to_python(dbus_status)
            if isinstance(status_str, str) and status_str:
                import json
                status = json.loads(status_str)
            else:
                status = status_str if isinstance(status_str, dict) else {}

            if isinstance(status, dict):
                # Backward-compatible fields expected by older SDK tests/callers.
                if "state" not in status:
                    models = status.get("models", [])
                    available_models = status.get("available_models", None)
                    has_models = False
                    if isinstance(models, list):
                        has_models = len(models) > 0
                    elif isinstance(available_models, int):
                        has_models = available_models > 0
                    status["state"] = "online" if has_models else "offline"

                if "message" not in status:
                    status["message"] = (
                        "Service has available models"
                        if status.get("state") == "online"
                        else "Service has no available models"
                    )

            return status
        except dbus.DBusException as e:
            raise self._handle_dbus_error(e)
        except Exception as e:
            raise ServerError(f"Unexpected error: {e}")

    def __enter__(self):
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        # Cleanup if needed
        return False