"""
Data types for SysAI SDK

Copyright (C) 2025 CTyunOS. All Rights Reserved.
"""

from dataclasses import dataclass
from typing import Optional, List, Dict, Any


# ============================================================================
# Exception Types
# ============================================================================

class SysAIError(Exception):
    """Base exception for SysAI SDK"""
    pass


class SysAIConnectionError(SysAIError):
    """D-Bus connection failed"""
    pass


class ServiceUnavailableError(SysAIError):
    """Service not available"""
    pass


class InvalidRequestError(SysAIError):
    """Invalid request parameters"""
    pass


class SysAITimeoutError(SysAIError):
    """Request timeout"""
    pass


class ModelNotFoundError(SysAIError):
    """Model not found"""
    pass


class ServerError(SysAIError):
    """Server internal error"""
    pass
