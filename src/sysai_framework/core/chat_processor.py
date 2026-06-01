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

    Key improvements over base RequestProcessor:
    1. Clear separation of streaming vs non-streaming logic
    2. Proper response wrapping for each mode
    3. Chat-specific parameter extraction
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
            # Hooks run alongside the main request without blocking
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

            # Stage 4: Wrap response based on streaming flag (at the end)
            # For streaming: wrap as StreamingResponse, for non-streaming: return dict
            return await self._wrap_response(response)

        except Exception as e:
            # Execute failure hooks
            await self._handle_failure(e)
            raise

    async def _wrap_response(self, response):
        """
        Wrap response based on streaming flag

        For streaming responses, wraps the async generator as StreamingResponse
        with appropriate headers. For non-streaming, returns the response dict directly.

        Args:
            response: Response from router (AsyncGenerator for streaming, dict for non-streaming)

        Returns:
            StreamingResponse for streaming, dict for non-streaming
        """
        if self.is_streaming:
            # Generate custom headers (before streaming starts)
            custom_headers = ResponseHeaderManager.get_streaming_headers(
                request_id=self.context.request_id,
                model_name=self.context.model,
                provider=self.context.provider,
            )

            logger.debug(
                f"[{self.context.request_id}] Wrapping response as StreamingResponse"
            )

            # Wrap with safe streaming response (handles first-chunk error detection)
            return await create_streaming_response(
                generator=response,
                headers=custom_headers
            )
        else:
            logger.debug(
                f"[{self.context.request_id}] Returning response dict"
            )
            return response

    def _extract_route_params(self) -> dict:
        """
        Extract chat completion specific parameters

        Returns:
            Dictionary of chat completion parameters (including stream flag)
        """
        return {
            'model': self.data.get('model'),
            'messages': self.data.get('messages'),
            'stream': self.data.get('stream', False),  # Include stream flag
            'temperature': self.data.get('temperature'),
            'max_tokens': self.data.get('max_tokens'),
            'top_p': self.data.get('top_p'),
            'stop': self.data.get('stop'),
            'presence_penalty': self.data.get('presence_penalty'),
            'frequency_penalty': self.data.get('frequency_penalty'),
            'user': self.data.get('user'),
            'thinking_budget': self.data.get('thinking_budget'),
            'reasoning': self.data.get('reasoning'),
            'tools': self.data.get('tools'),
            'tool_choice': self.data.get('tool_choice'),
            'parallel_tool_calls': self.data.get('parallel_tool_calls'),
        }


# Example: Future processor for image generation
class ImageGenerationProcessor(RequestProcessor):
    """
    Image generation processor (example for future extension)

    This demonstrates how to create specialized processors for different request types.
    """

    def _extract_route_params(self) -> dict:
        """Extract image generation parameters"""
        return {
            'model': self.data.get('model'),
            'prompt': self.data.get('prompt'),
            'n': self.data.get('n', 1),
            'size': self.data.get('size', '1024x1024'),
            'quality': self.data.get('quality', 'standard'),
        }

    async def _route_streaming(self, router_instance, params: dict):
        """Image generation typically doesn't support streaming"""
        raise NotImplementedError("Image generation does not support streaming")

    async def _route_non_streaming(self, router_instance, params: dict):
        """Route image generation request"""
        # Hypothetical method
        return router_instance.route_image_generation(**params)


# Example: Future processor for embeddings
class EmbeddingProcessor(RequestProcessor):
    """
    Embedding processor (example for future extension)

    This demonstrates how to create specialized processors for embeddings.
    """

    def _extract_route_params(self) -> dict:
        """Extract embedding parameters"""
        return {
            'model': self.data.get('model'),
            'input': self.data.get('input'),
            'encoding_format': self.data.get('encoding_format', 'float'),
        }

    async def _route_streaming(self, router_instance, params: dict):
        """Embeddings don't support streaming"""
        raise NotImplementedError("Embeddings do not support streaming")

    async def _route_non_streaming(self, router_instance, params: dict):
        """Route embedding request"""
        # Hypothetical method
        return router_instance.route_embedding(**params)
