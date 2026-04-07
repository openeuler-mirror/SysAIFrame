"""
Copyright (C) 2025 CTyunOS. All Rights Reserved.
File: request_processor.py
Desc: Unified request processor for SysAIFrame
     Manages the complete request lifecycle with hook support
Date: 2025-10-22
Author: Liu Mingran
"""

import asyncio
import time
import logging
from typing import Dict, Any, Optional
from fastapi import Request
from datetime import datetime

from sysai_framework.core.hooks import HookManager, get_hook_manager
from sysai_framework.core.response_headers import ResponseHeaderManager
from sysai_framework.core.exceptions import handle_exception_with_logging

logger = logging.getLogger(__name__)


class RequestContext:
    """
    Request context - carries information throughout request lifecycle

    This object is passed through all hooks and processing stages,
    allowing hooks to read and modify request/response data.
    """

    def __init__(self):
        """Initialize request context with default values"""
        self.request_id: Optional[str] = None
        self.start_time: Optional[datetime] = None
        self.model: Optional[str] = None
        self.user_id: Optional[str] = None
        self.provider: Optional[str] = None
        self.metadata: Dict[str, Any] = {}
        self.metrics: Dict[str, Any] = {}
        self.custom_headers: Dict[str, str] = {}

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert context to dictionary

        Returns:
            Dictionary representation of context
        """
        return {
            'request_id': self.request_id,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'model': self.model,
            'user_id': self.user_id,
            'provider': self.provider,
            'metadata': self.metadata,
            'metrics': self.metrics,
            'custom_headers': self.custom_headers,
        }


class RequestProcessor:
    """
    Unified request processor - manages complete request lifecycle

    This class provides a centralized way to handle all chat completion
    requests with support for hooks, monitoring, and error handling.
    """

    def __init__(self, request_data: Dict[str, Any], hook_manager: Optional[HookManager] = None):
        """
        Initialize request processor

        Args:
            request_data: Request data dictionary
            hook_manager: Optional hook manager (uses global if not provided)
        """
        self.data = request_data
        self.context = RequestContext()
        self.hook_manager = hook_manager or get_hook_manager()

        # Extract basic info
        self.context.request_id = request_data.get('request_id')
        self.context.model = request_data.get('model')
        self.context.start_time = datetime.now()

    async def process_request(
        self,
        fastapi_request: Request,
        router_instance,
        authorization: Optional[str] = None
    ):
        """
        Main request processing entry point

        Executes the complete request lifecycle:
        1. Pre-call processing and hooks
        2. Parallel execution: during-call hooks + actual request
        3. Post-call processing and hooks

        Args:
            fastapi_request: Original FastAPI request object
            router_instance: Model router instance
            authorization: Authorization header (optional)

        Returns:
            Response from backend (or error)

        Raises:
            Various exceptions that will be handled by error middleware
        """
        try:
            await self._pre_call_processing(fastapi_request, authorization)
            response = await self._execute_with_hooks(router_instance)
            final_response = await self._post_call_processing(response)
            return final_response
        except Exception as e:
            await self._handle_failure(e)
            raise

    async def _pre_call_processing(
        self,
        fastapi_request: Request,
        authorization: Optional[str] = None
    ):
        """
        Pre-call processing stage

        Performs:
        - User authentication
        - Request validation
        - Metadata injection
        - Pre-call hooks execution

        Args:
            fastapi_request: Original FastAPI request
            authorization: Authorization header
        """
        logger.debug(f"[{self.context.request_id}] Starting pre-call processing")

        # 1. Extract user information
        if authorization:
            self.context.user_id = await self._extract_user_id(authorization)

        # 2. Add metadata to request
        self.data['metadata'] = {
            'request_id': self.context.request_id,
            'user_id': self.context.user_id,
            'timestamp': self.context.start_time.isoformat(),
        }

        # 3. Build hook context
        hook_context = {
            'data': self.data,
            'request_id': self.context.request_id,
            'fastapi_request': fastapi_request,
            'user_id': self.context.user_id,
            'model': self.context.model,
        }

        # 4. Execute pre-call hooks
        hook_context = await self.hook_manager.execute_pre_call_hooks(hook_context)

        # 5. Update data from hooks (hooks may have modified it)
        self.data = hook_context['data']

        logger.debug(f"[{self.context.request_id}] Pre-call processing completed")

    async def _execute_with_hooks(self, router_instance):
        """
        Execute request with parallel during-call hooks

        This method must be implemented by subclasses to define
        how to execute the actual request along with during-call hooks.

        Subclasses should:
        1. Build hook context
        2. Create parallel tasks for hooks and actual request
        3. Execute with asyncio.gather()
        4. Return the response

        Args:
            router_instance: Router instance

        Returns:
            Response from backend (format depends on subclass)

        Raises:
            NotImplementedError: If subclass doesn't implement this method
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement _execute_with_hooks() method"
        )

    async def _post_call_processing(self, response):
        """
        Post-call processing stage

        Performs:
        - Response validation
        - Metrics collection
        - Custom headers generation
        - Post-call hooks execution

        Args:
            response: Response from backend

        Returns:
            Final processed response
        """
        logger.debug(f"[{self.context.request_id}] Starting post-call processing")

        # 1. Calculate metrics
        duration_ms = (datetime.now() - self.context.start_time).total_seconds() * 1000
        self.context.metrics = {
            'duration_ms': duration_ms,
            'model': self.context.model,
        }

        # 2. Extract token usage from response
        token_usage = None
        if isinstance(response, dict) and 'usage' in response:
            token_usage = response['usage']
            self.context.metrics['token_usage'] = token_usage

            # Record token usage Prometheus metrics
            try:
                from sysai_framework.core.metrics import token_usage_total
                model_name = self.context.model or "unknown"
                prompt_tokens = token_usage.get('prompt_tokens', 0)
                completion_tokens = token_usage.get('completion_tokens', 0)
                if prompt_tokens:
                    token_usage_total.labels(
                        model=model_name, token_type="prompt"
                    ).inc(prompt_tokens)
                if completion_tokens:
                    token_usage_total.labels(
                        model=model_name, token_type="completion"
                    ).inc(completion_tokens)
            except ImportError:
                pass

        # 3. Generate custom headers
        self.context.custom_headers = ResponseHeaderManager.get_custom_headers(
            request_id=self.context.request_id,
            model_name=self.context.model,
            provider=self.context.provider,
            duration_ms=duration_ms,
            token_usage=token_usage,
        )

        # 4. Build hook context
        hook_context = {
            'data': self.data,
            'response': response,
            'request_id': self.context.request_id,
            'model': self.context.model,
            'user_id': self.context.user_id,
            'duration_ms': duration_ms,
            'token_usage': token_usage,
        }

        # 5. Execute post-call hooks
        hook_context = await self.hook_manager.execute_post_call_hooks(hook_context)

        # 6. Update response from hooks (hooks may have modified it)
        response = hook_context['response']

        # 7. Log completion
        logger.debug(
            f"[{self.context.request_id}] Request completed: "
            f"duration={duration_ms:.2f}ms, "
            f"tokens={token_usage.get('total_tokens', 0) if token_usage else 0}"
        )

        logger.debug(f"[{self.context.request_id}] Post-call processing completed")
        return response

    async def _handle_failure(self, error: Exception):
        """
        Handle request failure

        Executes failure hooks and logs error

        Args:
            error: Exception that occurred
        """
        logger.error(
            f"[{self.context.request_id}] Request failed: {error}",
            exc_info=True
        )

        # Build failure context
        hook_context = {
            'data': self.data,
            'error': error,
            'request_id': self.context.request_id,
            'model': self.context.model,
            'user_id': self.context.user_id,
        }

        # Execute failure hooks
        try:
            await self.hook_manager.execute_failure_hooks(hook_context)
        except Exception as hook_error:
            logger.error(
                f"[{self.context.request_id}] Failure hook execution failed: {hook_error}",
                exc_info=True
            )

    async def _extract_user_id(self, authorization: str) -> Optional[str]:
        """Extract user ID from authorization header"""
        pass

    def get_context(self) -> RequestContext:
        """Get the request context"""
        return self.context

    def get_custom_headers(self) -> Dict[str, str]:
        """Get custom headers for response"""
        return self.context.custom_headers
