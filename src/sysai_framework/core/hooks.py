"""
Copyright (C) 2025 CTyunOS. All Rights Reserved.
File: hooks.py
Desc: Hook system for SysAIFrame
     Extensible hook mechanism for request processing lifecycle
Date: 2025-10-22
Author: Liu Mingran
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List, Callable
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class BaseHook(ABC):
    """Base hook class - all hooks must inherit from this"""

    def __init__(self, name: Optional[str] = None):
        """
        Initialize hook

        Args:
            name: Optional name for the hook (for logging)
        """
        self.name = name or self.__class__.__name__
        self.enabled = True

    @abstractmethod
    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute hook logic

        Args:
            context: Request context dictionary containing:
                - data: Request data
                - request_id: Unique request ID
                - fastapi_request: Original FastAPI request object
                - response: Response data (for post-call hooks)
                - etc.

        Returns:
            Modified context dictionary
        """
        pass

    def disable(self):
        """Disable this hook"""
        self.enabled = False

    def enable(self):
        """Enable this hook"""
        self.enabled = True


class PreCallHook(BaseHook):
    """
    Pre-call hook - executed before request is sent to backend

    Use cases:
    - Request parameter validation
    - Add metadata to request
    - Content filtering
    - Permission checking
    - Model alias resolution
    """

    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute pre-call hook

        Available context:
        - data: Request data (model, messages, etc.)
        - request_id: Unique request ID
        - fastapi_request: Original FastAPI request
        - user_id: User ID (if authenticated)
        """
        logger.debug(f"[{context.get('request_id')}] Executing pre-call hook: {self.name}")

        return context


class DuringCallHook(BaseHook):
    """
    During-call hook - executed in parallel with actual backend call

    Use cases:
    - Content moderation
    - Real-time monitoring
    - Cache warming
    - Analytics logging
    - Async notifications
    """

    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute during-call hook (runs in parallel with main request)

        Available context:
        - data: Request data
        - request_id: Unique request ID
        - model: Model name
        - user_id: User ID
        """
        logger.debug(f"[{context.get('request_id')}] Executing during-call hook: {self.name}")

        return context

    async def _check_content_safety(self, content: str) -> bool:
        """
        Check content safety (placeholder)

        Args:
            content: Text content to check

        Returns:
            True if content passes safety check, False otherwise
        """
        return True


class PostCallHook(BaseHook):
    """
    Post-call hook - executed after receiving response from backend

    Use cases:
    - Response filtering/modification
    - Logging and auditing
    - Billing/cost calculation
    - Caching response
    - Metrics collection
    - Success notifications
    """

    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute post-call hook

        Available context:
        - data: Original request data
        - response: Backend response
        - request_id: Unique request ID
        - duration_ms: Request duration
        - model: Model name
        - user_id: User ID
        """
        logger.debug(f"[{context.get('request_id')}] Executing post-call hook: {self.name}")

        return context

    async def _log_token_usage(self, request_id: str, usage: dict):
        """
        Log token usage (placeholder)

        Args:
            request_id: Request ID
            usage: Token usage dictionary
        """
        logger.info(
            f"[{request_id}] Token usage: "
            f"prompt={usage.get('prompt_tokens', 0)}, "
            f"completion={usage.get('completion_tokens', 0)}, "
            f"total={usage.get('total_tokens', 0)}"
        )


class FailureHook(BaseHook):
    """
    Failure hook - executed when request fails

    Use cases:
    - Error logging
    - Alert notifications
    - Fallback logic
    - Error metrics
    """

    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute failure hook

        Available context:
        - data: Original request data
        - error: Exception object
        - request_id: Unique request ID
        - model: Model name
        """
        logger.debug(f"[{context.get('request_id')}] Executing failure hook: {self.name}")

        return context


class HookManager:
    """
    Hook manager - manages and executes all hooks

    This is the central component for the hook system, allowing
    registration and execution of hooks at different lifecycle stages.
    """

    def __init__(self):
        """Initialize hook manager with empty hook lists"""
        self.pre_call_hooks: List[PreCallHook] = []
        self.during_call_hooks: List[DuringCallHook] = []
        self.post_call_hooks: List[PostCallHook] = []
        self.failure_hooks: List[FailureHook] = []
