"""
Copyright (C) 2025 CTyunOS. All Rights Reserved.
File: transformation.py
Desc: OpenAI-like provider configuration
      For generic Chat Completion API compatible endpoints
      Based on litellm.llms.openai_like.chat.transformation with stub modifications
Date: 2025-11-17
Author: Liu Mingran
"""

from typing import TYPE_CHECKING, Any, List, Optional, Tuple, Union

import httpx

from sysai_framework.llms.base.utils import get_secret_str
from sysai_framework.llms.base.types import AllMessageValues, ChatCompletionAssistantMessage

from ...openai.chat.gpt_transformation import OpenAIGPTConfig

# --- Stub for litellm types ---
# from litellm.types.utils import ModelResponse  # Disabled for SysAIFrame
ModelResponse = dict

if TYPE_CHECKING:
    from litellm.litellm_core_utils.litellm_logging import Logging as _LiteLLMLoggingObj

    LiteLLMLoggingObj = _LiteLLMLoggingObj
else:
    LiteLLMLoggingObj = Any


class OpenAILikeChatConfig(OpenAIGPTConfig):
    """
    Configuration for Chat Completion API compatible endpoints.

    This class is used for any provider that follows the Chat Completion API specification
    but is not one of the specifically supported providers (DashScope, Moonshot, etc.).

    Examples of compatible providers:
    - vLLM
    - LocalAI
    - LM Studio
    - Ollama (with OpenAI compatibility mode)
    - Any custom Chat Completion API compatible server
    """

    def _get_openai_compatible_provider_info(
        self,
        api_base: Optional[str],
        api_key: Optional[str],
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Get api_base and api_key for Chat Completion API compatible providers.
        """
        api_base = api_base or get_secret_str("OPENAI_LIKE_API_BASE")  # type: ignore
        dynamic_api_key = (
            api_key or get_secret_str("OPENAI_LIKE_API_KEY") or ""
        )  # vllm does not require an api key
        return api_base, dynamic_api_key

    @staticmethod
    def _json_mode_convert_tool_response_to_message(
        message: ChatCompletionAssistantMessage, json_mode: bool
    ) -> ChatCompletionAssistantMessage:
        """
        If json_mode is true, convert the returned tool call response to a content with json str.
        """
        if not json_mode:
            return message

        _tool_calls = message.get("tool_calls")

        if _tool_calls is None or len(_tool_calls) != 1:
            return message

        message["content"] = _tool_calls[0]["function"].get("arguments") or ""
        message["tool_calls"] = None

        return message

    @staticmethod
    def _sanitize_usage_obj(response_json: dict) -> dict:
        """
        Checks for a 'usage' object in the response and replaces any None token
        values with 0. This enforces OpenAI compatibility for providers that
        might return null.
        """
        if "usage" in response_json and isinstance(response_json.get("usage"), dict):
            usage = response_json["usage"]
            for key, value in usage.items():
                if key.endswith("_tokens") and value is None:
                    usage[key] = 0
        return response_json

    @staticmethod
    def _transform_response(
        model: str,
        response: httpx.Response,
        model_response: ModelResponse,
        stream: bool,
        logging_obj: LiteLLMLoggingObj,
        optional_params: dict,
        api_key: Optional[str],
        data: Union[dict, str],
        messages: List,
        print_verbose,
        encoding,
        json_mode: Optional[bool],
        custom_llm_provider: Optional[str],
        base_model: Optional[str],
    ) -> ModelResponse:
        """Unified response transformation for OpenAI-like providers."""
        response_json = response.json()

        # Sanitize the usage object
        response_json = OpenAILikeChatConfig._sanitize_usage_obj(response_json)

        if json_mode:
            for choice in response_json["choices"]:
                message = (
                    OpenAILikeChatConfig._json_mode_convert_tool_response_to_message(
                        choice.get("message"), json_mode
                    )
                )
                choice["message"] = message

        returned_response = ModelResponse(**response_json)

        if custom_llm_provider is not None:
            returned_response.model = (
                custom_llm_provider + "/" + (returned_response.model or "")
            )

        if base_model is not None:
            returned_response._hidden_params["model"] = base_model
        return returned_response

    def transform_response(
        self,
        model: str,
        raw_response: httpx.Response,
        model_response: ModelResponse,
        logging_obj: LiteLLMLoggingObj,
        request_data: dict,
        messages: List[AllMessageValues],
        optional_params: dict,
        litellm_params: dict,
        encoding: Any,
        api_key: Optional[str] = None,
        json_mode: Optional[bool] = None,
    ) -> ModelResponse:
        return OpenAILikeChatConfig._transform_response(
            model=model,
            response=raw_response,
            model_response=model_response,
            stream=optional_params.get("stream", False),
            logging_obj=logging_obj,
            optional_params=optional_params,
            api_key=api_key,
            data=request_data,
            messages=messages,
            print_verbose=None,
            encoding=None,
            json_mode=json_mode,
            custom_llm_provider=None,
            base_model=None,
        )

    def map_openai_params(
        self,
        non_default_params: dict,
        optional_params: dict,
        model: str,
        drop_params: bool,
        replace_max_completion_tokens_with_max_tokens: bool = True,
    ) -> dict:
        """
        Map OpenAI params for OpenAI-like providers.

        Most OpenAI-compatible providers support 'max_tokens' not 'max_completion_tokens'.
        """
        mapped_params = super().map_openai_params(
            non_default_params, optional_params, model, drop_params
        )
        if (
            "max_completion_tokens" in non_default_params
            and replace_max_completion_tokens_with_max_tokens
        ):
            mapped_params["max_tokens"] = non_default_params[
                "max_completion_tokens"
            ]
            mapped_params.pop("max_completion_tokens", None)

        return mapped_params