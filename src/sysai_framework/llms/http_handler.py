"""
HTTP Handler for LLM API Calls

Unified HTTP handler for provider API calls with request/response transformation.
"""

import json
import logging
import time
from typing import Any, Dict, List, Optional, Union, AsyncGenerator
import httpx

from sysai_framework.llms.base.transformation import BaseConfig
from sysai_framework.core.exceptions import (
    RetriableError, NonRetriableError,
    InvalidRequestError, AuthenticationError,
    RateLimitError, ServiceUnavailableError, TimeoutError
)

logger = logging.getLogger(__name__)


def _convert_http_status_to_exception(status_code: int, error_msg: str) -> Exception:
    """
    Convert HTTP status code to appropriate exception type.
    """
    if status_code == 400:
        return InvalidRequestError(f"Invalid request: {error_msg}")
    elif status_code == 401:
        return AuthenticationError(f"Authentication failed: {error_msg}")
    elif status_code == 403:
        return NonRetriableError(f"Forbidden: {error_msg}")
    elif status_code == 404:
        return NonRetriableError(f"Resource not found: {error_msg}")
    elif status_code == 422:
        return InvalidRequestError(f"Unprocessable entity: {error_msg}")
    elif status_code == 429:
        return RateLimitError(f"Rate limit exceeded: {error_msg}")
    elif status_code == 500:
        return ServiceUnavailableError(f"Internal server error: {error_msg}")
    elif status_code == 502:
        return ServiceUnavailableError(f"Bad gateway: {error_msg}")
    elif status_code == 503:
        return ServiceUnavailableError(f"Service unavailable: {error_msg}")
    elif status_code == 504:
        return TimeoutError(f"Gateway timeout: {error_msg}")
    else:
        return NonRetriableError(f"HTTP {status_code}: {error_msg}")


class LLMHTTPHandler:
    """
    LLM HTTP Handler
    """

    def __init__(self):
        self.sync_client: Optional[httpx.Client] = None
        self.async_client: Optional[httpx.AsyncClient] = None
