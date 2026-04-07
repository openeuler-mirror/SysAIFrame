"""
Copyright (C) 2025 CTyunOS. All Rights Reserved.
File: chat_processor.py
Desc: Chat completion specific request processor for SysAIFrame
     Specialized processor for chat completion requests
Date: 2025-10-22
Author: Liu Mingran
"""

import asyncio
import logging
from typing import Dict, Any, Optional
from fastapi import Request
from fastapi.responses import StreamingResponse

from sysai_framework.core.request_processor import RequestProcessor
from sysai_framework.core.streaming_utils import create_streaming_response
from sysai_framework.core.response_headers import ResponseHeaderManager

logger = logging.getLogger(__name__)


class ChatCompletionProcessor(RequestProcessor):
    """
    Chat completion specific processor

    This processor is specialized for handling chat completion requests,
    providing clear separation between streaming and non-streaming flows.
    """

    def __init__(self, request_data: Dict[str, Any], hook_manager=None):
        """
        Initialize chat completion processor

        Args:
            request_data: Chat completion request data
            hook_manager: Optional hook manager
        """
        super().__init__(request_data, hook_manager)
        self.is_streaming = request_data.get('stream', False)

    async def process_request(
        self,
        fastapi_request: Request,
        router_instance,
        authorization: Optional[str] = None
    ):
        """
        Process chat completion request - unified flow

        Flow:
        1. Pre-call processing
        2. Execute request with parallel during-call hooks
        3. Post-call processing (only for non-streaming)
        4. Wrap response based on streaming flag

        Args:
            fastapi_request: Original FastAPI request
            router_instance: Model router instance
            authorization: Authorization header

        Returns:
            StreamingResponse for streaming, dict for non-streaming
        """
        try:
            # Stage 1: Pre-call processing
            await self._pre_call_processing(fastapi_request, authorization)

            # Stage 2: Execute request with parallel during-call hooks
            logger.debug(f"[{self.context.request_id}] Starting request execution")

            # Build hook context
            hook_context = {
                'data': self.data,
                'request_id': self.context.request_id,
                'model': self.context.model,
                'user_id': self.context.user_id,
            }

            # Extract parameters (includes stream flag)
            params = self._extract_route_params()

            # Execute in parallel: during-call hooks + actual request
            results = await asyncio.gather(
                self.hook_manager.execute_during_call_hooks(hook_context),
                router_instance.route_chat_acompletion(**params),
                return_exceptions=True
            )

            # Check for errors in main request (results[1])
            response = results[1]
            if isinstance(response, Exception):
                raise response

            logger.debug(
                f"[{self.context.request_id}] Request execution completed, "
                f"response type: {type(response).__name__}"
            )

            # Stage 3: Post-call processing (only for non-streaming)
            if not self.is_streaming:
                response = await self._post_call_processing(response)

            # Stage 4: Wrap response based on streaming flag
            return await self._wrap_response(response)

        except Exception as e:
            # Execute failure hooks
            await self._handle_failure(e)
            raise

    async def _wrap_response(self, response):
        """
        Wrap response based on streaming flag

        Args:
            response: Response data (dict or async generator)

        Returns:
            StreamingResponse for streaming, dict for non-streaming
        """
        if self.is_streaming:
            headers = ResponseHeaderManager.get_streaming_headers(
                request_id=self.context.request_id,
                model_name=self.context.model,
            )
            return StreamingResponse(
                response,
                media_type="text/event-stream",
                headers=headers,
                status_code=200
            )
        return response

    def _extract_route_params(self) -> dict:
        """
        Extract chat completion specific parameters

        Returns:
            Dictionary of parameters for router call
        """
        params = {
            'model': self.data.get('model'),
            'stream': self.is_streaming,
        }
        if 'messages' in self.data:
            params['messages'] = self.data['messages']
        optional_params = [
            'temperature', 'top_p', 'max_tokens', 'stop',
            'frequency_penalty', 'presence_penalty', 'user'
        ]
        for param in optional_params:
            if param in self.data:
                params[param] = self.data[param]
        return params


class ImageGenerationProcessor(RequestProcessor):
    """
    Image generation processor (example for future extension)

    This processor handles image generation requests.
    """

    def __init__(self, request_data: Dict[str, Any], hook_manager=None):
        """
        Initialize image generation processor

        Args:
            request_data: Image generation request data
            hook_manager: Optional hook manager
        """
        super().__init__(request_data, hook_manager)
        self.is_streaming = request_data.get('stream', False)

    def _extract_route_params(self) -> dict:
        """
        Extract image generation parameters

        Returns:
            Dictionary of parameters for image generation
        """
        params = {'model': self.data.get('model')}
        if 'prompt' in self.data:
            params['prompt'] = self.data['prompt']
        optional_params = ['size', 'n', 'quality', 'style', 'response_format']
        for param in optional_params:
            if param in self.data:
                params[param] = self.data[param]
        return params

    async def _route_streaming(self, router_instance, params: dict):
        """
        Image generation typically doesn't support streaming

        Args:
            router_instance: Router instance
            params: Request parameters

        Returns:
            Non-streaming response
        """
        return await self._route_non_streaming(router_instance, params)

    async def _route_non_streaming(self, router_instance, params: dict):
        """
        Route image generation request

        Args:
            router_instance: Router instance
            params: Request parameters

        Returns:
            Image generation response
        """
        return await router_instance.route_image_generation(**params)


class EmbeddingProcessor(RequestProcessor):
    """
    Embedding processor (example for future extension)

    This processor handles embedding requests for vector search.
    """

    def __init__(self, request_data: Dict[str, Any], hook_manager=None):
        """
        Initialize embedding processor

        Args:
            request_data: Embedding request data
            hook_manager: Optional hook manager
        """
        super().__init__(request_data, hook_manager)

    def _extract_route_params(self) -> dict:
        """Extract embedding parameters"""
        pass

    async def _route_streaming(self, router_instance, params: dict):
        """Embeddings don't support streaming"""
        pass

    async def _route_non_streaming(self, router_instance, params: dict):
        """Route embedding request"""
        pass
