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

        logger.debug("HookManager initialized")

    def register_pre_call_hook(self, hook: PreCallHook):
        """
        Register a pre-call hook

        Args:
            hook: PreCallHook instance
        """
        self.pre_call_hooks.append(hook)
        logger.debug(f"Registered pre-call hook: {hook.name}")

    def register_during_call_hook(self, hook: DuringCallHook):
        """
        Register a during-call hook

        Args:
            hook: DuringCallHook instance
        """
        self.during_call_hooks.append(hook)
        logger.debug(f"Registered during-call hook: {hook.name}")

    def register_post_call_hook(self, hook: PostCallHook):
        """
        Register a post-call hook

        Args:
            hook: PostCallHook instance
        """
        self.post_call_hooks.append(hook)
        logger.debug(f"Registered post-call hook: {hook.name}")

    def register_failure_hook(self, hook: FailureHook):
        """
        Register a failure hook

        Args:
            hook: FailureHook instance
        """
        self.failure_hooks.append(hook)
        logger.debug(f"Registered failure hook: {hook.name}")

    async def execute_pre_call_hooks(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute all pre-call hooks sequentially

        Args:
            context: Request context

        Returns:
            Modified context after all hooks
        """
        for hook in self.pre_call_hooks:
            if hook.enabled:
                try:
                    context = await hook.execute(context)
                except Exception as e:
                    logger.error(
                        f"[{context.get('request_id')}] Pre-call hook {hook.name} failed: {e}",
                        exc_info=True
                    )
        return context

    async def execute_during_call_hooks(self, context: Dict[str, Any]):
        """
        Execute all during-call hooks in parallel

        These hooks run alongside the main request and should not
        block the main request flow.

        Args:
            context: Request context (copied to avoid modifications)
        """
        tasks = []
        for hook in self.during_call_hooks:
            if hook.enabled:
                tasks.append(self._execute_during_hook_safe(hook, context.copy()))

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _execute_during_hook_safe(self, hook: DuringCallHook, context: Dict[str, Any]):
        """
        Safely execute a during-call hook with error handling

        Args:
            hook: Hook to execute
            context: Request context
        """
        try:
            await hook.execute(context)
        except Exception as e:
            logger.error(
                f"[{context.get('request_id')}] During-call hook {hook.name} failed: {e}",
                exc_info=True
            )

    async def execute_post_call_hooks(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute all post-call hooks sequentially

        Args:
            context: Request context with response

        Returns:
            Modified context after all hooks
        """
        for hook in self.post_call_hooks:
            if hook.enabled:
                try:
                    context = await hook.execute(context)
                except Exception as e:
                    logger.error(
                        f"[{context.get('request_id')}] Post-call hook {hook.name} failed: {e}",
                        exc_info=True
                    )
        return context

    async def execute_failure_hooks(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute all failure hooks sequentially

        Args:
            context: Request context with error information

        Returns:
            Modified context after all hooks
        """
        for hook in self.failure_hooks:
            if hook.enabled:
                try:
                    context = await hook.execute(context)
                except Exception as e:
                    logger.error(
                        f"[{context.get('request_id')}] Failure hook {hook.name} failed: {e}",
                        exc_info=True
                    )
        return context

    def clear_hooks(self):
        """Clear all registered hooks"""
        self.pre_call_hooks.clear()
        self.during_call_hooks.clear()
        self.post_call_hooks.clear()
        self.failure_hooks.clear()
        logger.debug("All hooks cleared")

    def get_hook_summary(self) -> Dict[str, int]:
        """
        Get summary of registered hooks

        Returns:
            Dictionary with hook counts
        """
        return {
            "pre_call": len([h for h in self.pre_call_hooks if h.enabled]),
            "during_call": len([h for h in self.during_call_hooks if h.enabled]),
            "post_call": len([h for h in self.post_call_hooks if h.enabled]),
            "failure": len([h for h in self.failure_hooks if h.enabled]),
        }