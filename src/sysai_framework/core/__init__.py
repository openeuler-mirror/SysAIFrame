"""
Copyright (C) 2025 CTyunOS. All Rights Reserved.
File: __init__.py
Desc: Core module initialization for SysAIFrame
     Enhanced request processing, error handling and utilities
Date: 2025-10-22
Author: Liu Mingran
"""

from sysai_framework.core.exceptions import (
    CompatibleException,
    ModelNotFoundError,
    InvalidRequestError,
    AuthenticationError,
    RateLimitError,
    ServiceUnavailableError,
    TimeoutError,
    handle_exception_with_logging
)

from sysai_framework.core.response_headers import ResponseHeaderManager

from sysai_framework.core.streaming_utils import (
    create_streaming_response,
    wrap_generator_with_error_handling,
    format_sse_chunk,
    format_sse_done
)

from sysai_framework.core.hooks import (
    BaseHook,
    PreCallHook,
    DuringCallHook,
    PostCallHook,
    FailureHook,
    HookManager,
    get_hook_manager
)

from sysai_framework.core.request_processor import (
    RequestContext,
    RequestProcessor
)

from sysai_framework.core.chat_processor import (
    ChatCompletionProcessor,
    ImageGenerationProcessor,
    EmbeddingProcessor
)

__all__ = [
    # Exceptions
    "CompatibleException",
    "ModelNotFoundError",
    "InvalidRequestError",
    "AuthenticationError",
    "RateLimitError",
    "ServiceUnavailableError",
    "TimeoutError",
    "handle_exception_with_logging",

    # Response Headers
    "ResponseHeaderManager",

    # Streaming Utils
    "create_streaming_response",
    "wrap_generator_with_error_handling",
    "format_sse_chunk",
    "format_sse_done",

    # Hooks
    "BaseHook",
    "PreCallHook",
    "DuringCallHook",
    "PostCallHook",
    "FailureHook",
    "HookManager",
    "get_hook_manager",

    # Request Processors
    "RequestContext",
    "RequestProcessor",
    "ChatCompletionProcessor",
    "ImageGenerationProcessor",
    "EmbeddingProcessor",
]
