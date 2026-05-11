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


class ChatMessage(BaseModel):
    """Chat message in response"""
    role: str
    content: str


class ChatChoice(BaseModel):
    """Single completion choice"""
    index: int
    message: ChatMessage
    finish_reason: Optional[str] = None


class UsageInfo(BaseModel):
    """Token usage information"""
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class ChatCompletionResponse(BaseModel):
    """Chat completion response model - Chat Completion API compatible"""
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: List[ChatChoice]
    usage: UsageInfo


class DeltaMessage(BaseModel):
    """Delta message for streaming response"""
    role: Optional[str] = None
    content: Optional[str] = None


class ChatChoiceChunk(BaseModel):
    """Single completion choice chunk for streaming"""
    index: int
    delta: DeltaMessage
    finish_reason: Optional[str] = None


class ChatCompletionChunk(BaseModel):
    """Chat completion chunk model for streaming - Chat Completion API compatible"""
    id: str
    object: str = "chat.completion.chunk"
    created: int
    model: str
    choices: List[ChatChoiceChunk]


class ErrorResponse(BaseModel):
    """Error response model"""
    error: Dict[str, Any]


# ============================================================================
# API Endpoints
# ============================================================================

@router.post(
    "/chat/completions",
    response_model=ChatCompletionResponse,
    responses={
        200: {"description": "Successful completion"},
        400: {"description": "Bad request", "model": ErrorResponse},
        401: {"description": "Unauthorized"},
        500: {"description": "Internal server error", "model": ErrorResponse}
    },
    summary="Create chat completion",
    description="Creates a completion for the chat message, Chat Completion API compatible"
)
async def chat_completion(
    request: ChatCompletionRequest,
    fastapi_request: Request,
    authorization: Optional[str] = Header(None, description="Bearer token for authentication")
):
    """
    Create a chat completion

    This endpoint is Chat Completion API compatible.
    Supports both streaming and non-streaming responses.

    """
