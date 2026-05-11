"""
Copyright (C) 2025 CTyunOS. All Rights Reserved.
File: chat.py
Desc: Chat completion API endpoints for SysAIFrame
     Implements Chat Completion API compatible interface
Date: 2025-10-22
Author: Liu Mingran
"""

from fastapi import APIRouter, Header, HTTPException, status, Request
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Union
import logging
import time
import uuid

from sysai_framework.router.model_router import get_router
from sysai_framework.core import (
    handle_exception_with_logging,
    get_hook_manager
)
from sysai_framework.core.chat_processor import ChatCompletionProcessor

logger = logging.getLogger(__name__)

router = APIRouter()


# ============================================================================
# Pydantic Data Models
# ============================================================================

class Message(BaseModel):
    """Chat message model"""
    role: str = Field(..., description="Role of the message sender (system/user/assistant)")
    content: str = Field(..., description="Content of the message")
    name: Optional[str] = Field(None, description="Optional name of the sender")

    class Config:
        schema_extra = {
            "example": {
                "role": "user",
                "content": "Hello, how are you?"
            }
        }


class ChatCompletionRequest(BaseModel):
    """Chat completion request model - Chat Completion API compatible"""
    model: str = Field(..., description="Model name to use for completion")
    messages: List[Message] = Field(..., description="List of messages in the conversation")
    temperature: Optional[float] = Field(1.0, ge=0.0, le=2.0, description="Sampling temperature")
    max_tokens: Optional[int] = Field(None, gt=0, description="Maximum tokens to generate")
    top_p: Optional[float] = Field(1.0, ge=0.0, le=1.0, description="Nucleus sampling parameter")
    n: Optional[int] = Field(1, ge=1, description="Number of completions to generate")
    stream: Optional[bool] = Field(False, description="Enable streaming response")
    stop: Optional[Union[str, List[str]]] = Field(None, description="Stop sequences")
    presence_penalty: Optional[float] = Field(0.0, ge=-2.0, le=2.0, description="Presence penalty")
    frequency_penalty: Optional[float] = Field(0.0, ge=-2.0, le=2.0, description="Frequency penalty")
    logit_bias: Optional[Dict[str, float]] = Field(None, description="Logit bias map")
    user: Optional[str] = Field(None, description="User identifier")

    class Config:
        schema_extra = {
            "example": {
                "model": "deepseek-chat",
                "messages": [
                    {"role": "system", "content": "You are a helpful Linux expert."},
                    {"role": "user", "content": "Explain the Linux scheduler"}
                ],
                "temperature": 0.7,
                "max_tokens": 512,
                "stream": False
            }
        }


