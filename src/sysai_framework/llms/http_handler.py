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
from sysai_framework.config.model_config import DEFAULT_ROUTING_TIMEOUT
from sysai_framework.core.exceptions import (
    RetriableError, NonRetriableError,
    InvalidRequestError, AuthenticationError,
    RateLimitError, ServiceUnavailableError, TimeoutError
)

logger = logging.getLogger(__name__)

# Timeout constants for HTTP connections
# These are independent of model-level timeout because they control
# connection-establishment and data-transfer phases, not response-generation duration.
DEFAULT_CONNECT_TIMEOUT = 10.0    # TCP + TLS handshake timeout (seconds)
DEFAULT_POOL_TIMEOUT = 5.0        # Connection pool acquire timeout (seconds)
DEFAULT_WRITE_TIMEOUT = 30.0      # Request body send timeout (seconds)


def _convert_http_status_to_exception(status_code: int, error_msg: str) -> Exception:
    """
    Convert HTTP status code to appropriate exception type

    Args:
        status_code: HTTP status code
        error_msg: Error message

    Returns:
        Appropriate exception (RetriableError or NonRetriableError)
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
        # Unknown status code: treat as non-retriable by default
        return NonRetriableError(f"HTTP {status_code}: {error_msg}")


class LLMHTTPHandler:
    """
    LLM HTTP Handler

    Unified HTTP handler for making LLM API calls with provider-specific
    request/response transformation.
    """

    def __init__(self):
        self.sync_client: Optional[httpx.Client] = None
        self.async_client: Optional[httpx.AsyncClient] = None

    def _get_sync_client(self) -> httpx.Client:
        """Get or create synchronous HTTP client"""
        if self.sync_client is None:
            self.sync_client = httpx.Client(
                timeout=httpx.Timeout(
                    timeout=float(DEFAULT_ROUTING_TIMEOUT),
                    connect=DEFAULT_CONNECT_TIMEOUT,
                    read=float(DEFAULT_ROUTING_TIMEOUT),
                    write=DEFAULT_WRITE_TIMEOUT,
                    pool=DEFAULT_POOL_TIMEOUT
                ),
                follow_redirects=True
            )
        return self.sync_client

    def _get_async_client(self) -> httpx.AsyncClient:
        """Get or create asynchronous HTTP client"""
        if self.async_client is None:
            self.async_client = httpx.AsyncClient(
                timeout=httpx.Timeout(
                    timeout=float(DEFAULT_ROUTING_TIMEOUT),
                    connect=DEFAULT_CONNECT_TIMEOUT,
                    read=float(DEFAULT_ROUTING_TIMEOUT),
                    write=DEFAULT_WRITE_TIMEOUT,
                    pool=DEFAULT_POOL_TIMEOUT
                ),
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
        timeout: float = float(DEFAULT_ROUTING_TIMEOUT),
        **kwargs
    ) -> Union[Dict[str, Any], AsyncGenerator[str, None]]:
        """
        Unified completion call interface

        Complete flow:
        1. validate_environment - Validate environment and set headers
        2. get_complete_url - Get complete API URL
        3. transform_request - Transform request format
        4. HTTP call - Execute HTTP request
        5. transform_response - Transform response format (if needed)

        Args:
            provider_config: Provider configuration instance
            model: Model name
            messages: Message list
            api_base: API base URL
            api_key: API key
            optional_params: Optional parameters
            stream: Whether to stream response
            timeout: Timeout in seconds

        Returns:
            Dict for non-streaming, AsyncGenerator for streaming
        """
        try:
            # Step 1: Validate environment and get headers
            logger.debug("Step 1: Validating environment")
            headers = provider_config.validate_environment(
                api_key=api_key,
                headers={},
                model=model,
                messages=messages,
                optional_params=optional_params,
                litellm_params={},
                api_base=api_base
            )

            # Step 2: Get complete URL
            logger.debug("Step 2: Getting complete URL")
            complete_url = provider_config.get_complete_url(
                api_base=api_base,
                api_key=api_key,
                model=model,
                optional_params=optional_params,
                litellm_params={},
                stream=stream
            )

            # Step 3: Transform request data
            logger.debug("Step 3: Transforming request")
            # Ensure stream parameter is included in optional_params
            if stream:
                optional_params["stream"] = True

            request_data = provider_config.transform_request(
                model=model,
                messages=messages,
                optional_params=optional_params,
                litellm_params={},
                headers=headers
            )

            logger.debug(f"Calling {complete_url} with provider: {provider_config.__class__.__name__}")

            # Step 4 & 5: HTTP call and response transformation
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

    def _sync_call(
        self,
        provider_config: BaseConfig,
        url: str,
        headers: Dict[str, str],
        data: Dict[str, Any],
        timeout: float,
        model: str,
        messages: List[Dict[str, Any]],
        optional_params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Synchronous non-streaming call"""
        client = self._get_sync_client()

        try:
            # Convert float timeout to httpx.Timeout object
            # httpx.Timeout uses independent phase timing (connect/read/write/pool), not cumulative
            # connect/write/pool use fixed constants, read equals total_timeout (full response wait)
            if isinstance(timeout, (int, float)):
                total_timeout = float(timeout)
                timeout_obj = httpx.Timeout(
                    timeout=total_timeout,
                    connect=DEFAULT_CONNECT_TIMEOUT,
                    read=total_timeout,
                    write=DEFAULT_WRITE_TIMEOUT,
                    pool=DEFAULT_POOL_TIMEOUT
                )
            else:
                # If already a Timeout object, use it directly
                timeout_obj = timeout

            logger.debug(
                f"HTTP request timeout: timeout={getattr(timeout_obj, 'timeout', 'N/A')}s, "
                f"connect={timeout_obj.connect}s, read={timeout_obj.read}s"
            )

            # Execute HTTP POST request
            response = client.post(
                url=url,
                headers=headers,
                json=data,
                timeout=timeout_obj
            )

            logger.debug(f"Response received: status={response.status_code}")

            response.raise_for_status()

            content_length = response.headers.get('content-length')
            if content_length:
                size_mb = int(content_length) / (1024 * 1024)
                logger.debug(f"Response size: {size_mb:.2f} MB")

            # Get raw response
            raw_response = response.json()

            # Note: We directly return the raw response here
            # because Chat Completion API compatible response format is already standard
            # If provider_config has transform_response method, we can call it
            # But currently our BaseConfig doesn't have this method

            return raw_response

        except httpx.RemoteProtocolError as e:
            error_msg = (
                f"Backend service at {url} disconnected unexpectedly. "
                f"This may indicate the service is not running, crashed, or does not support this request. "
                f"Error: {str(e)}"
            )
            logger.error(error_msg)
            raise ServiceUnavailableError(error_msg)
        except httpx.ConnectError as e:
            error_msg = (
                f"Failed to connect to backend service at {url}. "
                f"Please check if the service is running and the endpoint URL is correct. "
                f"Error: {str(e)}"
            )
            logger.error(error_msg)
            raise ServiceUnavailableError(error_msg)
        except httpx.TimeoutException as e:
            error_msg = (
                f"Request to {url} timed out after {timeout} seconds. "
                f"The backend service may be overloaded or network is slow. "
                f"Error: {str(e)}"
            )
            logger.error(error_msg)
            raise TimeoutError(error_msg)
        except httpx.HTTPStatusError as e:
            status_code = e.response.status_code
            logger.error(f"HTTP error: {status_code}")

            # Get error message from response if available
            try:
                error_data = e.response.json()
                error_msg = error_data.get('error', {}).get('message', str(e))
            except:
                error_msg = str(e)

            # Convert to appropriate exception type
            raise _convert_http_status_to_exception(status_code, error_msg)
        except Exception as e:
            logger.error(f"Request to {url} failed: {e}")
            raise

    async def _stream_call(
        self,
        provider_config: BaseConfig,
        url: str,
        headers: Dict[str, str],
        data: Dict[str, Any],
        timeout: float,
        model: str,
        messages: List[Dict[str, Any]],
        optional_params: Dict[str, Any]
    ) -> AsyncGenerator[str, None]:
        """Asynchronous streaming call"""
        client = self._get_async_client()

        try:
            # Convert float timeout to httpx.Timeout object (same logic as sync call)
            if isinstance(timeout, (int, float)):
                total_timeout = float(timeout)
                timeout_obj = httpx.Timeout(
                    timeout=total_timeout,
                    connect=DEFAULT_CONNECT_TIMEOUT,
                    read=total_timeout,
                    write=DEFAULT_WRITE_TIMEOUT,
                    pool=DEFAULT_POOL_TIMEOUT
                )
            else:
                timeout_obj = timeout

            logger.debug(
                f"HTTP streaming request timeout: timeout={getattr(timeout_obj, 'timeout', 'N/A')}s, "
                f"connect={timeout_obj.connect}s, read={timeout_obj.read}s"
            )

            # Execute streaming HTTP POST request
            async with client.stream(
                method="POST",
                url=url,
                headers=headers,
                json=data,
                timeout=timeout_obj
            ) as response:
                response.raise_for_status()

                logger.debug("Streaming response started")
                chunk_count = 0

                # Use aiter_lines() to read SSE stream line by line
                async for line in response.aiter_lines():
                    # Skip empty lines
                    if not line or line.strip() == "":
                        continue

                    # SSE format: "data: {json}"
                    if line.startswith("data: "):
                        data_str = line[6:]  # Remove "data: " prefix

                        # Check if it's the end marker
                        if data_str == "[DONE]":
                            yield "data: [DONE]\n\n"
                            logger.debug(f"Streaming completed with {chunk_count} chunks")
                            break

                        try:
                            # Validate JSON format
                            json.loads(data_str)
                            # Return complete SSE line (maintain SSE format)
                            chunk_count += 1
                            yield f"data: {data_str}\n\n"
                        except json.JSONDecodeError:
                            logger.warning(f"Invalid JSON in stream: {data_str[:100]}")
                            continue

                logger.debug(f"Streaming response completed with {chunk_count} chunks")

        except httpx.RemoteProtocolError as e:
            error_msg = (
                f"Backend service at {url} disconnected unexpectedly during streaming. "
                f"This may indicate the service crashed, closed the connection prematurely, "
                f"or does not support streaming responses. "
                f"Please check the backend service logs. Error: {str(e)}"
            )
            logger.error(error_msg)
            raise ServiceUnavailableError(error_msg)
        except httpx.ConnectError as e:
            error_msg = (
                f"Failed to connect to backend service at {url} for streaming request. "
                f"Please verify the service is running and the endpoint URL is correct. "
                f"Error: {str(e)}"
            )
            logger.error(error_msg)
            raise ServiceUnavailableError(error_msg)
        except httpx.TimeoutException as e:
            error_msg = (
                f"Streaming request to {url} timed out after {timeout} seconds. "
                f"The backend service may be overloaded, the network is slow, "
                f"or the response is taking too long to generate. "
                f"Consider increasing the timeout value. Error: {str(e)}"
            )
            logger.error(error_msg)
            raise TimeoutError(error_msg)
        except httpx.HTTPStatusError as e:
            status_code = e.response.status_code
            logger.error(f"HTTP error from {url}: {status_code}")

            # Get error message from response if available
            try:
                error_data = e.response.json()
                error_msg = error_data.get('error', {}).get('message', str(e))
            except:
                error_msg = str(e)

            # Convert to appropriate exception type
            raise _convert_http_status_to_exception(status_code, error_msg)
        except Exception as e:
            logger.error(f"Streaming request to {url} failed: {e}")
            raise

    def close(self):
        """Close HTTP clients"""
        if self.sync_client:
            self.sync_client.close()
        if self.async_client:
            import asyncio
            asyncio.create_task(self.async_client.aclose())


# Global singleton
_http_handler: Optional[LLMHTTPHandler] = None


def get_http_handler() -> LLMHTTPHandler:
    """Get HTTP handler singleton instance"""
    global _http_handler
    if _http_handler is None:
        _http_handler = LLMHTTPHandler()
    return _http_handler