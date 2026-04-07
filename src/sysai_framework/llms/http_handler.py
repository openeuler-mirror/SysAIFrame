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
            if isinstance(timeout, (int, float)):
                total_timeout = float(timeout)
                connect_timeout = min(10.0, total_timeout * 0.2)
                read_timeout = max(1.0, total_timeout - connect_timeout)
                timeout_obj = httpx.Timeout(
                    timeout=total_timeout,
                    connect=connect_timeout,
                    read=read_timeout,
                    write=total_timeout,
                    pool=5.0
                )
            else:
                timeout_obj = timeout
            async with client.stream(
                method="POST",
                url=url,
                headers=headers,
                json=data,
                timeout=timeout_obj
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line or line.strip() == "":
                        continue
                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str == "[DONE]":
                            yield "data: [DONE]\n\n"
                            break
                        try:
                            json.loads(data_str)
                            yield f"data: {data_str}\n\n"
                        except json.JSONDecodeError:
                            continue
        except httpx.RemoteProtocolError as e:
            error_msg = f"Backend service at {url} disconnected unexpectedly during streaming. Error: {str(e)}"
            logger.error(error_msg)
            raise ServiceUnavailableError(error_msg)
        except httpx.ConnectError as e:
            error_msg = f"Failed to connect to backend service at {url}. Error: {str(e)}"
            logger.error(error_msg)
            raise ServiceUnavailableError(error_msg)
        except httpx.TimeoutException as e:
            error_msg = f"Streaming request to {url} timed out after {timeout} seconds. Error: {str(e)}"
            logger.error(error_msg)
            raise TimeoutError(error_msg)
        except httpx.HTTPStatusError as e:
            status_code = e.response.status_code
            try:
                error_data = e.response.json()
                error_msg = error_data.get('error', {}).get('message', str(e))
            except:
                error_msg = str(e)
            raise _convert_http_status_to_exception(status_code, error_msg)
        except Exception as e:
            logger.error(f"Streaming request to {url} failed: {e}")
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
            if isinstance(timeout, (int, float)):
                total_timeout = float(timeout)
                connect_timeout = min(10.0, total_timeout * 0.2)
                read_timeout = max(1.0, total_timeout - connect_timeout)
                timeout_obj = httpx.Timeout(
                    timeout=total_timeout,
                    connect=connect_timeout,
                    read=read_timeout,
                    write=total_timeout,
                    pool=5.0
                )
            else:
                timeout_obj = timeout
            response = client.post(
                url=url,
                headers=headers,
                json=data,
                timeout=timeout_obj
            )
            response.raise_for_status()
            raw_response = response.json()
            return raw_response
        except httpx.RemoteProtocolError as e:
            error_msg = f"Backend service at {url} disconnected unexpectedly. Error: {str(e)}"
            logger.error(error_msg)
            raise ServiceUnavailableError(error_msg)
        except httpx.ConnectError as e:
            error_msg = f"Failed to connect to backend service at {url}. Error: {str(e)}"
            logger.error(error_msg)
            raise ServiceUnavailableError(error_msg)
        except httpx.TimeoutException as e:
            error_msg = f"Request to {url} timed out after {timeout} seconds. Error: {str(e)}"
            logger.error(error_msg)
            raise TimeoutError(error_msg)
        except httpx.HTTPStatusError as e:
            status_code = e.response.status_code
            try:
                error_data = e.response.json()
                error_msg = error_data.get('error', {}).get('message', str(e))
            except:
                error_msg = str(e)
            raise _convert_http_status_to_exception(status_code, error_msg)
        except Exception as e:
            logger.error(f"Request to {url} failed: {e}")
            raise
