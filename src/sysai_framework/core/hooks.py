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
