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
        name_to_error_type = {
            "MODEL_NOT_FOUND": "model_not_found_error",
            "VALIDATION_ERROR": "invalid_request_error",
            "INVALID_PARAMETER": "invalid_request_error",
            "TIMEOUT_ERROR": "timeout_error",
            "CONNECTION_ERROR": "service_unavailable_error",
            "NETWORK_ERROR": "service_unavailable_error",
            "INTERNAL_ERROR": "internal_error",
        }

        if status_obj.name in name_to_error_type:
            return name_to_error_type[status_obj.name]

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

        if status_obj:
            http_status = status_obj.http_status
            error_message = message or status_obj.message_template
            error_code = code or status_obj.code
            error_type_value = self._get_error_type_from_status_code(status_obj)
        else:
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

        if status_obj:
            detail["error"]["code_name"] = status_obj.name

        super().__init__(status_code=http_status, detail=detail)
