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
    
    def __init__(self, attempted_models: list):
        self.attempted_models = attempted_models
        super().__init__(f"All models failed after trying: {', '.join(attempted_models)}")


class CompatibleException(HTTPException):
    """
    Chat Completion API compatible exception class
    
    Supports both traditional parameters and StatusCode objects for better type safety.
    """
    
    @staticmethod
    def _get_error_type_from_status_code(status_obj: StatusCode) -> str:
        """
        Map StatusCode to appropriate error_type string
        
        Args:
            status_obj: StatusCode object
            
        Returns:
            Error type string compatible with Chat Completion API
        """
        # Map StatusCode name to error_type
        name_to_error_type = {
            "MODEL_NOT_FOUND": "model_not_found_error",
            "VALIDATION_ERROR": "invalid_request_error",
            "INVALID_PARAMETER": "invalid_request_error",
            "TIMEOUT_ERROR": "timeout_error",
            "CONNECTION_ERROR": "service_unavailable_error",
            "NETWORK_ERROR": "service_unavailable_error",
            "INTERNAL_ERROR": "internal_error",
        }
        
        # Try to get from name mapping first
        if status_obj.name in name_to_error_type:
            return name_to_error_type[status_obj.name]
        
        # Fallback to HTTP status code mapping
        http_status_to_error_type = {
            400: "invalid_request_error",
            401: "authentication_error",
            403: "permission_error",
            404: "not_found_error",
            429: "rate_limit_error",
            500: "internal_error",
            502: "bad_gateway_error",
            503: "service_unavailable_error",
            504: "timeout_error",
        }
        
        return http_status_to_error_type.get(
            status_obj.http_status,
            "internal_error"
        )
    
    def __init__(
        self,
        status_code: Optional[int] = None,
        message: Optional[str] = None,
        error_type: str = "invalid_request_error",
        param: Optional[str] = None,
        code: Optional[Union[str, int]] = None,
        status_obj: Optional[StatusCode] = None
    ):
        """
        Initialize Chat Completion API compatible exception
        
        Supports two modes:
        1. Traditional mode: Pass status_code, message, error_type, etc.
        2. StatusCode mode: Pass status_obj, and optionally override message/param
        
        Args:
            status_code: HTTP status code (optional if status_obj provided)
            message: Error message (optional if status_obj provided)
            error_type: Type of error (ignored if status_obj provided)
            param: Parameter that caused the error
            code: Error code (string or int, optional if status_obj provided)
            status_obj: StatusCode object (new recommended way)
        """
        self.status_obj = status_obj
        
        # If StatusCode object provided, use it
        if status_obj:
            http_status = status_obj.http_status
            error_message = message or status_obj.message_template
            error_code = code or status_obj.code
            error_type_value = self._get_error_type_from_status_code(status_obj)
        else:
            # Traditional mode
            http_status = status_code or 500
            error_message = message or "An error occurred"
            error_code = code or self._get_error_code(http_status)
            error_type_value = error_type
        
        detail = {
            "error": {
                "message": error_message,
                "type": error_type_value,
                "param": param,
                "code": error_code
            }
        }
        
        # Add status code name if using StatusCode object
        if status_obj:
            detail["error"]["code_name"] = status_obj.name
        
        super().__init__(status_code=http_status, detail=detail)
    
    @staticmethod
    def _get_error_code(status_code: int) -> str:
        """Get error code from HTTP status code (legacy support)"""
        code_map = {
            400: "invalid_request",
            401: "unauthorized",
            403: "forbidden",
            404: "not_found",
            429: "rate_limit_exceeded",
            500: "internal_error",
            502: "bad_gateway",
            503: "service_unavailable",
            504: "gateway_timeout"
        }
        return code_map.get(status_code, "unknown_error")
    
    @classmethod
    def from_status_code(
        cls, 
        status_obj: StatusCode, 
        param: Optional[str] = None,
        **format_kwargs
    ) -> "CompatibleException":
        """
        Create exception from StatusCode object with message formatting
        
        Args:
            status_obj: StatusCode object
            param: Parameter that caused the error
            **format_kwargs: Arguments for message template formatting
        
        Returns:
            CompatibleException instance
        """
        try:
            message = status_obj.message_template.format(**format_kwargs)
        except KeyError:
            message = status_obj.message_template
        
        return cls(status_obj=status_obj, message=message, param=param)


class ModelNotFoundError(CompatibleException):
    """Model not found error"""
    def __init__(self, model_name: str):
        super().__init__(
            status_obj=MODEL_NOT_FOUND,
            message=MODEL_NOT_FOUND.message_template.format(model=model_name),
            param="model"
        )


class InvalidRequestError(CompatibleException, NonRetriableError):
    """Invalid request error - non-retriable"""
    def __init__(self, message: str, param: Optional[str] = None):
        CompatibleException.__init__(
            self,
            status_obj=INVALID_PARAMETER,
            message=message,
            param=param
        )


class AuthenticationError(CompatibleException, NonRetriableError):
    """Authentication error - non-retriable"""
    def __init__(self, message: str = "Invalid authentication credentials"):
        CompatibleException.__init__(
            self,
            status_code=status.HTTP_401_UNAUTHORIZED,
            message=message,
            error_type="authentication_error"
        )


class RateLimitError(CompatibleException, RetriableError):
    """Rate limit exceeded error - retriable"""
    def __init__(self, message: str = "Rate limit exceeded"):
        CompatibleException.__init__(
            self,
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            message=message,
            error_type="rate_limit_error"
        )


class ServiceUnavailableError(CompatibleException, RetriableError):
    """Service unavailable error - retriable"""
    def __init__(self, message: str = "Service temporarily unavailable"):
        CompatibleException.__init__(
            self,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            message=message,
            error_type="service_unavailable_error"
        )


class TimeoutError(CompatibleException, RetriableError):
    """Request timeout error - retriable"""
    def __init__(self, message: str = "Request timeout"):
        CompatibleException.__init__(
            self,
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            message=message,
            error_type="timeout_error"
        )


async def handle_exception_with_logging(
    e: Exception,
    request_id: Optional[str] = None,
    model: Optional[str] = None,
    user_id: Optional[str] = None
) -> CompatibleException:
    """
    Unified exception handling with logging
    
    Converts various exception types to Chat Completion API compatible format
    and logs them with context information.
    
    Now uses StatusCode system instead of string matching for better reliability.
    Returns specific exception types when appropriate.
    
    Args:
        e: The exception to handle
        request_id: Request ID for tracking
        model: Model name
        user_id: User ID
        
    Returns:
        Chat Completion API compatible exception (specific type when possible)
    """
    from .status_codes import (
        TIMEOUT_ERROR, CONNECTION_ERROR, NETWORK_ERROR,
        VALIDATION_ERROR, INTERNAL_ERROR
    )
    
    # Build logging context
    extra_context = {}
    if request_id:
        extra_context['request_id'] = request_id
    if model:
        extra_context['model'] = model
    if user_id:
        extra_context['user_id'] = user_id
    
    # Log the exception
    logger.error(
        f"Request failed: {str(e)}",
        exc_info=True,
        extra=extra_context
    )
    
    # Convert to Chat Completion API compatible format
    if isinstance(e, CompatibleException):
        return e
    elif isinstance(e, RetriableError):
        # Retriable errors should be treated as service unavailable (503)
        error_msg = str(e) if str(e) else "Service temporarily unavailable"
        return ServiceUnavailableError(error_msg)
    elif isinstance(e, NonRetriableError):
        # Non-retriable errors might be 400 or 500 depending on context
        # Check if it's a validation error
        error_str = str(e).lower()
        if any(keyword in error_str for keyword in ["invalid", "validation", "missing", "required"]):
            error_msg = str(e) if str(e) else "Invalid request"
            return InvalidRequestError(error_msg)
        else:
            # Default to service unavailable for non-retriable errors
            error_msg = str(e) if str(e) else "Service error"
            return ServiceUnavailableError(error_msg)
    elif isinstance(e, HTTPException):
        return CompatibleException(
            status_code=e.status_code,
            message=str(e.detail),
            error_type="http_error"
        )
    elif isinstance(e, ValueError):
        # Return InvalidRequestError for ValueError
        error_msg = f"Validation failed: {str(e)}"
        return InvalidRequestError(error_msg)
    elif isinstance(e, KeyError):
        # Return InvalidRequestError for KeyError
        error_msg = f"Missing required field: {str(e)}"
        return InvalidRequestError(error_msg, param=str(e))
    
    # Check error message to determine exception type
    error_str = str(e).lower()
    error_type_str = type(e).__name__.lower()
    
    # Check for timeout-related errors
    if isinstance(e, (asyncio.TimeoutError, TimeoutError)) or "timeout" in error_str:
        error_msg = str(e) if str(e) else "Connection timeout"
        return TimeoutError(error_msg)
    
    # Check for connection/network-related errors
    # Prioritize service unavailable (503) over internal error (500)
    connection_keywords = [
        "connection", "refused", "unreachable", "network", 
        "disconnected", "connect", "failed to connect",
        "service unavailable", "backend service", "service is not running",
        "crashed", "closed the connection", "does not support"
    ]
    
    if isinstance(e, (ConnectionError, OSError, ConnectionRefusedError, ConnectionResetError)) or \
       any(keyword in error_str for keyword in connection_keywords) or \
       "connection" in error_type_str or "network" in error_type_str:
        if "network" in error_str:
            error_msg = str(e) if str(e) else "Network error"
        elif "refused" in error_str:
            error_msg = str(e) if str(e) else "Connection refused"
        elif "disconnected" in error_str or "disconnect" in error_str:
            error_msg = str(e) if str(e) else "Connection disconnected"
        else:
            error_msg = str(e) if str(e) else "Connection error"
        return ServiceUnavailableError(error_msg)
    
    # Check for service-related errors that should be 503
    service_unavailable_keywords = [
        "service unavailable", "service temporarily", "backend service",
        "service is not running", "service crashed", "service error",
        "unavailable", "not available", "no healthy", "all models failed"
    ]
    if any(keyword in error_str for keyword in service_unavailable_keywords):
        error_msg = str(e) if str(e) else "Service unavailable"
        return ServiceUnavailableError(error_msg)
    
    # For unknown exceptions, try to determine if it's likely a service issue
    # If the error message suggests a service/backend issue, return 503 instead of 500
    if any(keyword in error_str for keyword in ["backend", "upstream", "downstream", "external"]):
        error_msg = str(e) if str(e) else "Service error"
        return ServiceUnavailableError(error_msg)
    
    # Default internal error - use CompatibleException with internal_error type
    # Only use 500 for truly unexpected internal errors
    error_msg = str(e) if str(e) else "Unknown error"
    return CompatibleException(
        status_obj=INTERNAL_ERROR,
        message=f"Internal error: {error_msg}",
        error_type="internal_error"
    )

