"""
Copyright (C) 2025 CTyunOS. All Rights Reserved.
File: streaming_utils.py
Desc: Streaming utilities for SysAIFrame
     Safe streaming response with first-chunk error detection
Date: 2025-10-22
Author: Liu Mingran
"""

import json
import logging
from typing import AsyncGenerator, Union, Optional, Dict, Any
from fastapi.responses import StreamingResponse

logger = logging.getLogger(__name__)


async def create_streaming_response(
    generator: AsyncGenerator,
    headers: Optional[Dict[str, str]] = None,
    default_status_code: int = 200
) -> StreamingResponse:
    """
    Create a safe streaming response with first-chunk error detection

    Inspects the first chunk for errors and sets the HTTP status code accordingly.
    The entire original generator content is streamed, but the HTTP status code
    is set based on the first chunk if it's a recognized error.

    Args:
        generator: Async generator that yields chunks
        headers: Custom response headers
        default_status_code: Default HTTP status code

    Returns:
        StreamingResponse with appropriate status code
    """
    first_chunk = None
    status_code = default_status_code
    headers = headers or {}

    try:
        # Get the first chunk
        first_chunk = await generator.__anext__()

        # Check if first chunk contains an error
        if first_chunk:
            error_status = _check_chunk_for_error(first_chunk)
            if error_status:
                status_code = error_status
                logger.warning(
                    f"Error detected in first chunk: {status_code}",
                    extra={"status_code": status_code}
                )

    except StopAsyncIteration:
        # Generator is empty
        logger.warning("Generator exhausted before yielding any chunks")
        async def empty_gen():
            if False:
                yield
        return StreamingResponse(
            empty_gen(),
            headers=headers,
            status_code=200
        )

    except Exception as e:
        # Error reading first chunk
        logger.error(f"Error reading first chunk: {e}", exc_info=True)

        # Use StatusCode system instead of string matching
        from sysai_framework.core.status_codes import (
            CONNECTION_ERROR, TIMEOUT_ERROR, INTERNAL_ERROR, DISCONNECTED
        )

        # Determine error type based on exception type (not string matching)
        if isinstance(e, (ConnectionError, ConnectionRefusedError, ConnectionResetError)):
            status = CONNECTION_ERROR
        elif isinstance(e, TimeoutError):
            status = TIMEOUT_ERROR
        elif "RemoteProtocolError" in type(e).__name__ or "Disconnected" in str(e):
            # Handle httpx/h11 specific errors
            status = DISCONNECTED
        else:
            status = INTERNAL_ERROR

        error_message = status.message_template.format(details=str(e))

        async def error_gen():
            error_data = {
                "error": {
                    "message": error_message,
                    "type": status.level.value,
                    "code": status.code,
                    "code_name": status.name
                }
            }
            yield f"data: {json.dumps(error_data)}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(
            error_gen(),
            headers=headers,
            status_code=status.http_status
        )

    # Recombine generator with first chunk
    async def combined_generator():
        """Generator that yields first chunk then continues with original"""
        if first_chunk:
            yield first_chunk

        try:
            async for chunk in generator:
                yield chunk
        except Exception as e:
            # Handle errors in subsequent chunks
            logger.error(f"Error in streaming: {e}", exc_info=True)

            # Use StatusCode system instead of string matching
            from sysai_framework.core.status_codes import (
                CONNECTION_ERROR, TIMEOUT_ERROR, STREAM_ERROR, DISCONNECTED
            )

            # Determine error type based on exception type (not string matching)
            if isinstance(e, (ConnectionError, ConnectionRefusedError, ConnectionResetError)):
                status = CONNECTION_ERROR
            elif isinstance(e, TimeoutError):
                status = TIMEOUT_ERROR
            elif "RemoteProtocolError" in type(e).__name__ or "Disconnected" in str(e):
                status = DISCONNECTED
            else:
                status = STREAM_ERROR

            error_message = status.message_template.format(details=str(e))

            error_data = {
                "error": {
                    "message": error_message,
                    "type": status.level.value,
                    "code": status.code,
                    "code_name": status.name
                }
            }
            yield f"data: {json.dumps(error_data)}\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        combined_generator(),
        media_type="text/event-stream",
        headers=headers,
        status_code=status_code
    )


def _check_chunk_for_error(chunk: Union[str, dict]) -> Optional[int]:
    """
    Check if a chunk contains an error and extract status code

    Args:
        chunk: The chunk to check (string or dict)

    Returns:
        HTTP status code if error found, None otherwise
    """
    try:
        data = None

        # Parse chunk if it's a string
        if isinstance(chunk, str):
            # Handle SSE format
            if chunk.startswith("data: "):
                json_str = chunk[6:].strip()
                if json_str and json_str != "[DONE]":
                    data = json.loads(json_str)
                else:
                    return None
            else:
                # Try to parse as plain JSON
                try:
                    data = json.loads(chunk)
                except json.JSONDecodeError:
                    return None
        else:
            data = chunk

        # Check for error field
        if isinstance(data, dict) and "error" in data:
            error = data["error"]

            # Try to extract status code from error
            if isinstance(error, dict):
                # Check code field
                code = error.get("code")
                if isinstance(code, int) and 100 <= code <= 599:
                    return code

                # Map error type to status code
                error_type = error.get("type", "")
                return _map_error_type_to_status(error_type)

            # Default error status
            return 500

    except Exception as e:
        logger.debug(f"Failed to parse chunk for error: {e}")

    return None


def _map_error_type_to_status(error_type: str) -> int:
    """
    Map error type to HTTP status code

    Args:
        error_type: Error type string

    Returns:
        HTTP status code
    """
    error_map = {
        "invalid_request_error": 400,
        "authentication_error": 401,
        "permission_error": 403,
        "not_found_error": 404,
        "rate_limit_error": 429,
        "internal_error": 500,
        "service_unavailable": 503,
        "timeout_error": 504,
    }

    return error_map.get(error_type, 500)


async def wrap_generator_with_error_handling(
    generator: AsyncGenerator,
    request_id: Optional[str] = None
) -> AsyncGenerator:
    """Wrap an async generator with error handling"""
    pass


def format_sse_chunk(data: Dict[str, Any]) -> str:
    """Format data as Server-Sent Events chunk"""
    pass


def format_sse_done() -> str:
    """Format SSE done message"""
    pass
