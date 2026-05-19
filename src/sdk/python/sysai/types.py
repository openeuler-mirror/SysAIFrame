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


# ============================================================================
# Data Types
# ============================================================================

@dataclass
class ChatMessage:
    """Chat message"""
    role: str
    content: str
    name: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for D-Bus"""
        result = {"role": self.role, "content": self.content}
        if self.name:
            result["name"] = self.name
        return result

    @classmethod
    def user(cls, content: str, name: Optional[str] = None) -> "ChatMessage":
        """Create user message"""
        return cls(role="user", content=content, name=name)

    @classmethod
    def system(cls, content: str, name: Optional[str] = None) -> "ChatMessage":
        """Create system message"""
        return cls(role="system", content=content, name=name)

    @classmethod
    def assistant(cls, content: str, name: Optional[str] = None) -> "ChatMessage":
        """Create assistant message"""
        return cls(role="assistant", content=content, name=name)

