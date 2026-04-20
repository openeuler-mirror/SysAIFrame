"""
Copyright (C) 2025 CTyunOS. All Rights Reserved.
File: exceptions.py
Desc: Enhanced exception handling for SysAIFrame
     Chat Completion API compatible error responses and unified exception handling
     Now supports StatusCode dataclass for better type safety
Date: 2025-11-28
Author: Liu Mingran
"""

from fastapi import HTTPException, status
from typing import Optional, Dict, Any, Union
import logging
import asyncio

from .status_codes import StatusCode, INTERNAL_ERROR, INVALID_PARAMETER, MODEL_NOT_FOUND

logger = logging.getLogger(__name__)


class ModelError(Exception):
    """Base class for model errors"""
    pass


class RetriableError(ModelError):
    """Retriable error - can retry the operation"""
    pass


class NonRetriableError(ModelError):
    """Non-retriable error - should not retry"""
    pass


class AllModelsFailed(ModelError):
    """All models failed after trying all fallback options"""

    pass
