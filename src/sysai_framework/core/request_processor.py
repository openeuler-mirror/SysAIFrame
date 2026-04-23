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
    """Unified request processor - manages complete request lifecycle"""
    pass
