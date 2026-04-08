"""
Copyright (C) 2025 CTyunOS. All Rights Reserved.
File: chat_methods.py
Desc: D-Bus chat completion method implementation
Date: 2025-11-18
Author: Liu Mingran
"""

import logging
import json
import time
import uuid
from typing import Dict, Any

logger = logging.getLogger(__name__)

# Platform detection
try:
    import dbus
    import dbus.service
    DBUS_AVAILABLE = True
except ImportError:
    DBUS_AVAILABLE = False
    logger.warning("dbus-python not available")

from .type_converter import request_to_python, response_to_dbus
from .stream_handler import StreamHandler


class ChatServiceObject(dbus.service.Object if DBUS_AVAILABLE else object):
    """
    D-Bus service object implementing chat completion methods.
    """

    INTERFACE_NAME = 'org.ctyunos.AIGateway.Chat'

    def __init__(self, bus_name, object_path, gateway_app=None):
        """
        Initialize chat service object.

        Args:
            bus_name: D-Bus bus name
            object_path: D-Bus object path
            gateway_app: FastAPI application instance
        """
        if DBUS_AVAILABLE:
            super().__init__(bus_name, object_path)

        self.gateway_app = gateway_app
        self.stream_handler = StreamHandler(self)

        # Import dependencies
        try:
            from sysai_framework.config import get_config_manager
            from sysai_framework.router.model_router import ModelRouter

            self.config_manager = get_config_manager()
            self.model_router = ModelRouter(self.config_manager)

            logger.info("Chat service object initialized with dependencies")
        except Exception as e:
            logger.error(f"Failed to initialize dependencies: {e}", exc_info=True)
            self.config_manager = None
            self.model_router = None

    @dbus.service.method(
        dbus_interface=INTERFACE_NAME,
        in_signature='a{sv}',
        out_signature='a{sv}'
    )
    def ChatCompletion(self, request):
        """
        Perform chat completion.

        Args:
            request: D-Bus variant dict with request parameters

        Returns:
            D-Bus variant dict with response
        """
        try:
            # Convert D-Bus request to Python dict
            python_request = request_to_python(request)

            logger.info(f"ChatCompletion request: model={python_request.get('model', 'default')}, "
                       f"stream={python_request.get('stream', False)}")

            # Check if this is a streaming request
            is_streaming = python_request.get('stream', False)

            if is_streaming:
                return self._handle_streaming_request(python_request)
            else:
                return self._handle_non_streaming_request(python_request)

        except Exception as e:
            logger.error(f"ChatCompletion error: {e}", exc_info=True)
            error_response = {
                'error': {
                    'message': str(e),
                    'type': 'internal_error',
                    'code': 'dbus_error'
                }
            }
            return response_to_dbus(error_response)

    def _handle_non_streaming_request(self, request: Dict) -> Any:
        """
        Handle non-streaming chat completion request.

        Args:
            request: Python request dictionary

        Returns:
            D-Bus response
        """
        try:
            # Check if model router is initialized
            if not self.model_router:
                raise Exception("Model router not initialized")

            # Create a minimal request object
            from pydantic import BaseModel
            from typing import List, Optional

            class Message(BaseModel):
                role: str
                content: str

            class ChatRequest(BaseModel):
                model: Optional[str] = None
                messages: List[Message]
                temperature: Optional[float] = 0.7
                max_tokens: Optional[int] = 1000
                top_p: Optional[float] = 1.0
                stream: bool = False

            # Validate required fields
            if 'messages' not in request or not request['messages']:
                raise ValueError("'messages' field is required and cannot be empty")

            # Convert request to Pydantic model
            messages = [Message(**msg) for msg in request['messages']]
            chat_request = ChatRequest(
                model=request.get('model'),
                messages=messages,
                temperature=request.get('temperature', 0.7),
                max_tokens=request.get('max_tokens', 1000),
                top_p=request.get('top_p', 1.0),
                stream=False
            )

            # Process request using existing processor
            # Note: This is synchronous, which is appropriate for D-Bus method calls
            result = self.model_router.route_chat_completion(
                model=chat_request.model,
                messages=[msg.dict() for msg in chat_request.messages],
                temperature=chat_request.temperature,
                max_tokens=chat_request.max_tokens,
                top_p=chat_request.top_p,
                stream=False
            )

            # Convert result to response format
            if isinstance(result, dict):
                response = result
            else:
                # If result is a string or other type, wrap it
                response = {
                    'id': f'chatcmpl-{uuid.uuid4().hex[:8]}',
                    'object': 'chat.completion',
                    'created': int(time.time()),
                    'model': chat_request.model or 'default',
                    'choices': [{
                        'index': 0,
                        'message': {
                            'role': 'assistant',
                            'content': str(result)
                        },
                        'finish_reason': 'stop'
                    }]
                }

            return response_to_dbus(response)

        except Exception as e:
            logger.error(f"Non-streaming request error: {e}", exc_info=True)
            raise

    def _handle_streaming_request(self, request: Dict) -> Any:
        """
        Handle streaming chat completion request.

        Args:
            request: Python request dictionary

        Returns:
            D-Bus response with initial metadata (id, model)
        """
        try:
            # Validate required fields
            if 'messages' not in request or not request['messages']:
                raise ValueError("'messages' field is required and cannot be empty")

            # Generate request ID
            request_id = f'chatcmpl-{uuid.uuid4().hex[:8]}'

            # Return initial response immediately
            initial_response = {
                'id': request_id,
                'object': 'chat.completion',
                'created': int(time.time()),
                'model': request.get('model', 'default')
            }

            # Start streaming in background
            self.stream_handler.start_stream(request_id, request)

            return response_to_dbus(initial_response)

        except Exception as e:
            logger.error(f"Streaming request error: {e}", exc_info=True)
            raise

    @dbus.service.method(
        dbus_interface=INTERFACE_NAME,
        in_signature='',
        out_signature='as'
    )
    def GetChatModels(self):
        """
        Get list of available chat models.

        Returns:
            D-Bus array of model names
        """
        try:
            if not self.config_manager:
                logger.warning("Config manager not available")
                return dbus.Array(['mock'], signature='s')

            models = self.config_manager.get_available_models()

            # Convert to D-Bus string array
            from .type_converter import models_to_dbus
            return models_to_dbus(models)

        except Exception as e:
            logger.error(f"GetChatModels error: {e}", exc_info=True)
            return dbus.Array([], signature='s')

    @dbus.service.method(
        dbus_interface=INTERFACE_NAME,
        in_signature='',
        out_signature='a{sv}'
    )
    def GetStatus(self):
        """
        Get gateway status information.

        Returns:
            D-Bus variant dict with status
        """
        try:
            status = {
                'service': 'sysaiframe-gateway',
                'status': 'running',
                'dbus_interface': 'active',
                'timestamp': int(time.time())
            }

            if self.config_manager:
                models = self.config_manager.get_available_models()
                status['available_models'] = len(models)
                status['models'] = models

                # Get default model
                default_model = self.config_manager.get_default_model()
                if default_model:
                    status['default_model'] = default_model

            return response_to_dbus(status)

        except Exception as e:
            logger.error(f"GetStatus error: {e}", exc_info=True)
            error_status = {
                'status': 'error',
                'error': str(e)
            }
            return response_to_dbus(error_status)

    @dbus.service.signal(
        dbus_interface=INTERFACE_NAME,
        signature='sa{sv}'
    )
    def StreamChunk(self, request_id, chunk):
        """
        Signal emitted for each streaming response chunk.

        Args:
            request_id: Request ID
            chunk: Chunk data as variant dict
        """
        # This method is called to emit the signal
        # The actual signal emission is handled by dbus-python
        pass

    @dbus.service.signal(
        dbus_interface=INTERFACE_NAME,
        signature='sa{sv}'
    )
    def StreamDone(self, request_id, usage):
        """
        Signal emitted when streaming is complete.

        Args:
            request_id: Request ID
            usage: Token usage statistics as variant dict
        """
        # This method is called to emit the signal
        pass


