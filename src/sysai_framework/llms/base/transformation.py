"""
Copyright (C) 2025 CTyunOS. All Rights Reserved.
File: transformation.py
Desc: Base configuration and exception classes for LLM providers
      Based on litellm.llms.base_llm.chat.transformation with stub modifications
Date: 2025-11-17
Author: Liu Mingran
"""

import types
from abc import ABC, abstractmethod
from typing import (
    TYPE_CHECKING,
    Any,
    AsyncIterator,
    Iterator,
    List,
    Optional,
    Tuple,
    Type,
    Union,
    cast,
)

import httpx

from .types import (
    AllMessageValues,
    BaseLLMModelInfo,
    ChatCompletionToolChoiceFunctionParam,
    ChatCompletionToolChoiceObjectParam,
    ChatCompletionToolParam,
    ChatCompletionToolParamFunctionChunk,
)
from .utils import map_finish_reason, supports_reasoning

# --- Stub for litellm dependencies ---
# import litellm  # Disabled for SysAIFrame
# from litellm.constants import DEFAULT_MAX_TOKENS, RESPONSE_FORMAT_TOOL_NAME  # Disabled
# from litellm.llms.custom_httpx.http_handler import AsyncHTTPHandler, HTTPHandler  # Disabled
# from pydantic import BaseModel  # Disabled

DEFAULT_MAX_TOKENS = 4096
RESPONSE_FORMAT_TOOL_NAME = "json_tool_call"


def type_to_response_format_param(response_format=None):
    """Stub for litellm.type_to_response_format_param"""
    if response_format is None:
        return None
    if isinstance(response_format, dict):
        return response_format
    return None


def map_developer_role_to_system_role(messages: List[AllMessageValues]) -> List[AllMessageValues]:
    """Translate developer role to system role for non-OpenAI providers."""
    result = []
    for m in messages:
        if m.get("role") == "developer":
            result.append({"role": "system", "content": m.get("content")})
        else:
            result.append(m)
    return result


if TYPE_CHECKING:
    from litellm.litellm_core_utils.streaming_handler import CustomStreamWrapper
    from litellm.types.utils import ModelResponse
    from litellm.litellm_core_utils.litellm_logging import Logging as _LiteLLMLoggingObj

    LiteLLMLoggingObj = _LiteLLMLoggingObj
else:
    LiteLLMLoggingObj = Any


class BaseLLMException(Exception):
    """
    Base exception class for LLM provider errors.
    Provides Chat Completion API compatible error format.
    """

    def __init__(
        self,
        status_code: int,
        message: str,
        headers: Optional[Union[dict, httpx.Headers]] = None,
        request: Optional[httpx.Request] = None,
        response: Optional[httpx.Response] = None,
        body: Optional[dict] = None,
    ):
        self.status_code = status_code
        self.message: str = message
        self.headers = headers

        if request:
            self.request = request
        else:
            self.request = httpx.Request(
                method="POST", url="https://github.com/CTyunOS/SysAIFrame"
            )

        if response:
            self.response = response
        else:
            self.response = httpx.Response(
                status_code=status_code, request=self.request
            )

        self.body = body
        super().__init__(self.message)


class BaseConfig(ABC):
    """
    Base configuration class for all LLM providers.

    Subclasses must implement:
    - get_supported_openai_params(model): Return list of supported params
    - map_openai_params(...): Map params to provider-specific format
    - validate_environment(...): Set up headers for API request
    - transform_request(...): Transform request body
    - transform_response(...): Transform response
    - get_error_class(...): Return provider-specific error class
    """

    def __init__(self):
        pass

    @classmethod
    def get_config(cls):
        """Get configuration dict from class attributes."""
        return {
            k: v
            for k, v in cls.__dict__.items()
            if not k.startswith("__")
            and not k.startswith("_abc")
            and not k.startswith("_is_base_class")
            and not isinstance(
                v,
                (
                    types.FunctionType,
                    types.BuiltinFunctionType,
                    classmethod,
                    staticmethod,
                    property,
                ),
            )
            and v is not None
        }

    def get_json_schema_from_pydantic_object(
        self, response_format: Optional[Union[Type[Any], dict]]
    ) -> Optional[dict]:
        """Convert Pydantic/dict response_format to response_format parameter."""
        return type_to_response_format_param(response_format=response_format)

    def is_thinking_enabled(self, non_default_params: dict) -> bool:
        """Check if thinking/reasoning mode is enabled."""
        return (
            non_default_params.get("thinking", {}).get("type") == "enabled"
            or non_default_params.get("reasoning_effort") is not None
        )

    def is_max_tokens_in_request(self, non_default_params: dict) -> bool:
        """Check if max_tokens or max_completion_tokens is in request."""
        return (
            "max_tokens" in non_default_params
            or "max_completion_tokens" in non_default_params
        )

    def update_optional_params_with_thinking_tokens(
        self, non_default_params: dict, optional_params: dict
    ):
        """
        When thinking is enabled but max_tokens not specified,
        set max_tokens to thinking budget + DEFAULT_MAX_TOKENS.
        """
        is_thinking_enabled = self.is_thinking_enabled(optional_params)
        if is_thinking_enabled and (
            "max_tokens" not in non_default_params
            and "max_completion_tokens" not in non_default_params
        ):
            thinking_token_budget = cast(dict, optional_params["thinking"]).get(
                "budget_tokens", None
            )
            if thinking_token_budget is not None:
                optional_params["max_tokens"] = (
                    thinking_token_budget + DEFAULT_MAX_TOKENS
                )

    def should_fake_stream(
        self,
        model: Optional[str],
        stream: Optional[bool],
        custom_llm_provider: Optional[str] = None,
    ) -> bool:
        """Returns True if the model/provider should fake stream."""
        return False

    def _add_tools_to_optional_params(self, optional_params: dict, tools: List) -> dict:
        """Helper to add tools to optional_params."""
        if "tools" not in optional_params:
            optional_params["tools"] = tools
        else:
            optional_params["tools"] = [
                *optional_params["tools"],
                *tools,
            ]
        return optional_params

    def translate_developer_role_to_system_role(
        self,
        messages: List[AllMessageValues],
    ) -> List[AllMessageValues]:
        """Translate developer role to system role for non-OpenAI providers."""
        return map_developer_role_to_system_role(messages=messages)

    def should_retry_llm_api_inside_llm_translation_on_http_error(
        self, e: httpx.HTTPStatusError, litellm_params: dict
    ) -> bool:
        """Returns True if the request should be retried on UnprocessableEntityError."""
        return False

    def transform_request_on_unprocessable_entity_error(
        self, e: httpx.HTTPStatusError, request_data: dict
    ) -> dict:
        """Transform request data on UnprocessableEntityError."""
        return request_data

    @property
    def max_retry_on_unprocessable_entity_error(self) -> int:
        """Max retry count for UnprocessableEntityError."""
        return 0

    @abstractmethod
    def get_supported_openai_params(self, model: str) -> list:
        pass

    def _add_response_format_to_tools(
        self,
        optional_params: dict,
        value: dict,
        is_response_format_supported: bool,
        enforce_tool_choice: bool = True,
    ) -> dict:
        """
        Translate response_format to a tool call for providers
        that don't support response_format directly.
        """
        json_schema: Optional[dict] = None
        if "response_schema" in value:
            json_schema = value["response_schema"]
        elif "json_schema" in value:
            json_schema = value["json_schema"]["schema"]

        if json_schema and not is_response_format_supported:
            _tool_choice = ChatCompletionToolChoiceObjectParam(
                type="function",
                function=ChatCompletionToolChoiceFunctionParam(
                    name=RESPONSE_FORMAT_TOOL_NAME
                ),
            )

            _tool = ChatCompletionToolParam(
                type="function",
                function=ChatCompletionToolParamFunctionChunk(
                    name=RESPONSE_FORMAT_TOOL_NAME, parameters=json_schema
                ),
            )

            optional_params.setdefault("tools", [])
            optional_params["tools"].append(_tool)
            if enforce_tool_choice:
                optional_params["tool_choice"] = _tool_choice

            optional_params["json_mode"] = True
        elif is_response_format_supported:
            optional_params["response_format"] = value
        return optional_params

    @abstractmethod
    def map_openai_params(
        self,
        non_default_params: dict,
        optional_params: dict,
        model: str,
        drop_params: bool,
    ) -> dict:
        pass

    @abstractmethod
    def validate_environment(
        self,
        headers: dict,
        model: str,
        messages: List[AllMessageValues],
        optional_params: dict,
        litellm_params: dict,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
    ) -> dict:
        pass

    def sign_request(
        self,
        headers: dict,
        optional_params: dict,
        request_data: dict,
        api_base: str,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        stream: Optional[bool] = None,
        fake_stream: Optional[bool] = None,
    ) -> Tuple[dict, Optional[bytes]]:
        """Some providers require signing the request."""
        return headers, None

    def get_complete_url(
        self,
        api_base: Optional[str],
        api_key: Optional[str],
        model: str,
        optional_params: dict,
        litellm_params: dict,
        stream: Optional[bool] = None,
    ) -> str:
        """
        Construct complete API endpoint URL.

        For Chat Completion API compatible providers, this gets provider info
        and ensures URL ends with /chat/completions.
        """
        if not api_base:
            api_base, _ = self._get_openai_compatible_provider_info(api_base, api_key)

        if api_base and not api_base.endswith("/chat/completions"):
            api_base = api_base.rstrip("/")
            api_base = f"{api_base}/chat/completions"

        return api_base or "https://api.openai.com/v1/chat/completions"

    def _get_openai_compatible_provider_info(
        self,
        api_base: Optional[str],
        api_key: Optional[str],
    ) -> tuple[Optional[str], Optional[str]]:
        """
        Get default api_base and api_key for Chat Completion API compatible providers.
        Subclasses should override this to provide provider-specific defaults.
        """
        return api_base, api_key

    @abstractmethod
    def transform_request(
        self,
        model: str,
        messages: List[AllMessageValues],
        optional_params: dict,
        litellm_params: dict,
        headers: dict,
    ) -> dict:
        pass

    async def async_transform_request(
        self,
        model: str,
        messages: List[AllMessageValues],
        optional_params: dict,
        litellm_params: dict,
        headers: dict,
    ) -> dict:
        """Default: delegates to sync transform_request."""
        return self.transform_request(
            model=model,
            messages=messages,
            optional_params=optional_params,
            litellm_params=litellm_params,
            headers=headers,
        )

    @abstractmethod
    def transform_response(
        self,
        model: str,
        raw_response: httpx.Response,
        model_response: Any,
        logging_obj: LiteLLMLoggingObj,
        request_data: dict,
        messages: List[AllMessageValues],
        optional_params: dict,
        litellm_params: dict,
        encoding: Any,
        api_key: Optional[str] = None,
        json_mode: Optional[bool] = None,
    ) -> Any:
        pass

    @abstractmethod
    def get_error_class(
        self, error_message: str, status_code: int, headers: Union[dict, httpx.Headers]
    ) -> BaseLLMException:
        pass

    def get_model_response_iterator(
        self,
        streaming_response: Union[Iterator[str], AsyncIterator[str], Any],
        sync_stream: bool,
        json_mode: Optional[bool] = False,
    ) -> Any:
        pass

    async def get_async_custom_stream_wrapper(
        self,
        model: str,
        custom_llm_provider: str,
        logging_obj: LiteLLMLoggingObj,
        api_base: str,
        headers: dict,
        data: dict,
        messages: list,
        client: Optional[Any] = None,
        json_mode: Optional[bool] = None,
        signed_json_body: Optional[bytes] = None,
    ) -> Any:
        raise NotImplementedError

    def get_sync_custom_stream_wrapper(
        self,
        model: str,
        custom_llm_provider: str,
        logging_obj: LiteLLMLoggingObj,
        api_base: str,
        headers: dict,
        data: dict,
        messages: list,
        client: Optional[Any] = None,
        json_mode: Optional[bool] = None,
        signed_json_body: Optional[bytes] = None,
    ) -> Any:
        raise NotImplementedError

    @property
    def custom_llm_provider(self) -> Optional[str]:
        return None

    @property
    def has_custom_stream_wrapper(self) -> bool:
        return False

    @property
    def supports_stream_param_in_request_body(self) -> bool:
        """Most providers support stream parameter in request body."""
        return True

    def post_stream_processing(self, stream: Any) -> Any:
        """Hook for providers to post-process streaming responses."""
        return stream

    def calculate_additional_costs(
        self, model: str, prompt_tokens: int, completion_tokens: int
    ) -> Optional[dict]:
        """Calculate additional costs beyond standard token costs."""
        return None