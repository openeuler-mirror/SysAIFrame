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
    # Generate request ID for tracking
    request_id = f"req-{int(time.time())}-{uuid.uuid4().hex[:8]}"

    # Prepare request data - use Pydantic's dict() method to safely handle optional fields
    # exclude_none=True ensures None values are not included, preventing downstream issues
    request_dict = request.dict(exclude_none=True)

    # Build request_data with required fields and optional fields (only if provided)
    request_data = {
        'request_id': request_id,
        'model': request_dict['model'],
        'messages': [msg.dict() for msg in request.messages],
        'stream': request_dict.get('stream', False),  # Always include stream, default False
    }

    # Add optional fields that were provided (exclude_none=True already filtered them)
    optional_fields = ['temperature', 'max_tokens', 'top_p', 'stop',
                       'presence_penalty', 'frequency_penalty', 'user']
    for field in optional_fields:
        if field in request_dict:
            request_data[field] = request_dict[field]

    logger.debug(
        f"[{request_id}] Received chat completion request: model={request.model}, stream={request.stream}"
    )

    try:
        # Create chat-specific processor with global hook manager
        processor = ChatCompletionProcessor(request_data, hook_manager=get_hook_manager())

        # Get router instance
        router_instance = get_router()

        # Process request - processor handles streaming vs non-streaming internally
        # Returns StreamingResponse for streaming, dict for non-streaming
        return await processor.process_request(
            fastapi_request=fastapi_request,
            router_instance=router_instance,
            authorization=authorization
        )

    except Exception as e:
        logger.error(f"[{request_id}] Request failed: {e}", exc_info=True)

        # Check for AllModelsFailed exception (all fallback models failed)
        from sysai_framework.core.exceptions import AllModelsFailed
        if isinstance(e, AllModelsFailed):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "error": {
                        "message": f"All models failed after trying: {', '.join(e.attempted_models)}. Please check model configurations and API endpoints.",
                        "type": "service_unavailable_error",
                        "code": "all_models_failed",
                        "attempted_models": e.attempted_models
                    }
                }
            )

        # Check for specific error cases
        error_message = str(e).lower()

        # Get router instance for checking model count (if available)
        try:
            router_instance = get_router()
            model_count = len(router_instance.config_manager.models) if router_instance.config_manager.models else 0
        except Exception:
            # If we can't get router instance, assume no models
            model_count = 0

        # Case 1: No models configured
        # Check both error message and actual model count
        has_no_models = (
            "no models configured" in error_message or
            model_count == 0
        )

        if has_no_models:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "error": {
                        "message": "No models configured. Please add at least one model using 'ai-config model add'.",
                        "type": "no_models_configured",
                        "code": "service_unavailable"
                    }
                }
            )

        # Case 2: No available model found (could be no models or no healthy models)
        if "no available model found" in error_message:
            # Check if there are any models configured
            if model_count == 0:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail={
                        "error": {
                            "message": "No models configured. Please add at least one model using 'ai-config model add'.",
                            "type": "no_models_configured",
                            "code": "service_unavailable"
                        }
                    }
                )
            else:
                # Models are configured but none are available/healthy
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail={
                        "error": {
                            "message": "No healthy models available. Please check model health status.",
                            "type": "no_healthy_models",
                            "code": "service_unavailable"
                        }
                    }
                )

        # Case 3: No healthy models
        if "no healthy models" in error_message:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "error": {
                        "message": "No healthy models available. Please check model health status.",
                        "type": "no_healthy_models",
                        "code": "service_unavailable"
                    }
                }
            )

        # Convert to Chat Completion API compatible exception
        compatible_exception = await handle_exception_with_logging(
            e,
            request_id=request_id,
            model=request.model
        )
        raise compatible_exception


# ============================================================================
# Model Management Endpoints
# ============================================================================

@router.get(
    "/models",
    summary="List available models",
    description="Get list of available AI models"
)
async def list_models():
    """
    List available models

    Returns a list of models that can be used for chat completion.
    """
    try:
        router_instance = get_router()
        models = router_instance.get_available_models()

        # Format response according to Chat Completion API specification
        model_list = [
            {
                "id": model_name,
                "object": "model",
                "created": int(time.time()),
                "owned_by": "sysaiframe"
            }
            for model_name in models
        ]

        return {
            "object": "list",
            "data": model_list
        }

    except Exception as e:
        logger.error(f"Error listing models: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": {"message": "Failed to list models"}}
        )


@router.get(
    "/models/{model_name}",
    summary="Get model details",
    description="Get detailed information about a specific model"
)
async def get_model(model_name: str):
    """
    Get model details

    Returns detailed information about a specific model.
    """
    try:
        router_instance = get_router()
        model_config = router_instance.get_model_config(model_name)

        if not model_config:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": {"message": f"Model {model_name} not found"}}
            )

        return {
            "id": model_config.name,
            "object": "model",
            "created": int(time.time()),
            "owned_by": "sysaiframe",
            "provider": model_config.provider,
            "capabilities": model_config.capabilities,
            "supports_streaming": model_config.supports_streaming
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting model details: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": {"message": "Failed to get model details"}}
        )


@router.get("/status")
async def get_service_status():
    """
    Get service status

    Returns service state and model availability information.
    This endpoint can be used to check if the service has any configured models
    and whether they are healthy.

    Response fields:
    - state: Service state (initializing/ready/degraded/error)
    - total_models: Total number of configured models
    - healthy_models: Number of healthy models
    - error_message: Error message if service is in degraded/error state
    - last_update: Timestamp of last status update
    """
    try:
        from sysai_framework.core.service_status import get_service_status, update_service_status
        from sysai_framework.config import get_config_manager

        # Update status from current configuration
        config_manager = get_config_manager()
        update_service_status(config_manager)

        # Get status
        service_status = get_service_status()
        status_dict = service_status.to_dict()

        # Return appropriate HTTP status code based on service state
        http_status = status.HTTP_200_OK
        if service_status.is_degraded():
            http_status = status.HTTP_503_SERVICE_UNAVAILABLE

        return status_dict

    except Exception as e:
        logger.error(f"Error getting service status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": {"message": f"Failed to get service status: {str(e)}"}}
        )
