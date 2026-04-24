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

    def _get_sync_client(self) -> httpx.Client:
        """Get or create synchronous HTTP client"""
        if self.sync_client is None:
            self.sync_client = httpx.Client(
                timeout=httpx.Timeout(180.0, connect=10.0),
                follow_redirects=True
            )
        return self.sync_client

    def _get_async_client(self) -> httpx.AsyncClient:
        """Get or create asynchronous HTTP client"""
        if self.async_client is None:
            self.async_client = httpx.AsyncClient(
                timeout=httpx.Timeout(180.0, connect=10.0),
                follow_redirects=True
            )
        return self.async_client

    def completion(
        self,
        provider_config: BaseConfig,
        model: str,
        messages: List[Dict[str, Any]],
        api_base: str,
        api_key: str,
        optional_params: Dict[str, Any],
        stream: bool = False,
        timeout: float = 300.0,
        **kwargs
    ) -> Union[Dict[str, Any], AsyncGenerator[str, None]]:
        """
        Unified completion call interface
        """
        try:
            headers = provider_config.validate_environment(
                api_key=api_key,
                headers={},
                model=model,
                messages=messages,
                optional_params=optional_params,
                litellm_params={},
                api_base=api_base
            )
            complete_url = provider_config.get_complete_url(
                api_base=api_base,
                api_key=api_key,
                model=model,
                optional_params=optional_params,
                litellm_params={},
                stream=stream
            )
            if stream:
                optional_params["stream"] = True
            request_data = provider_config.transform_request(
                model=model,
                messages=messages,
                optional_params=optional_params,
                litellm_params={},
                headers=headers
            )
            if stream:
                return self._stream_call(
                    provider_config=provider_config,
                    url=complete_url,
                    headers=headers,
                    data=request_data,
                    timeout=timeout,
                    model=model,
                    messages=messages,
                    optional_params=optional_params
                )
            else:
                return self._sync_call(
                    provider_config=provider_config,
                    url=complete_url,
                    headers=headers,
                    data=request_data,
                    timeout=timeout,
                    model=model,
                    messages=messages,
                    optional_params=optional_params
                )
        except Exception as e:
            logger.error(f"Error in completion: {e}", exc_info=True)
            raise
