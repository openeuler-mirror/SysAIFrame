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
