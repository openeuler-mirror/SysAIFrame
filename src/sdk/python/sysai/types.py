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


@dataclass
class Usage:
    """Token usage statistics"""
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Usage":
        """Create from dictionary"""
        return cls(
            prompt_tokens=data.get("prompt_tokens", 0),
            completion_tokens=data.get("completion_tokens", 0),
            total_tokens=data.get("total_tokens", 0)
        )


@dataclass
class ChatResponse:
    """Chat completion response"""
    id: str
    model: str
    content: str
    finish_reason: Optional[str]
    usage: Usage
    raw_response: Dict[str, Any]

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ChatResponse":
        """Create from D-Bus response dictionary"""
        content = ""
        finish_reason = None
        if "choices" in data and data["choices"]:
            choice = data["choices"][0]
            if "message" in choice:
                content = choice["message"].get("content", "")
            finish_reason = choice.get("finish_reason")
            if finish_reason == "":
                finish_reason = None

        usage_data = data.get("usage", {})
        usage = Usage.from_dict(usage_data)

        return cls(
            id=data.get("id", ""),
            model=data.get("model", ""),
            content=content,
            finish_reason=finish_reason,
            usage=usage,
            raw_response=data
        )

