"""
Copyright (C) 2026 CTyunOS. All Rights Reserved.
File: transformation.py
Desc: Volcengine (ByteDance/豆包) chat completion transformation
      Based on litellm.llms.volcengine.chat.transformation
      Support for thinking parameter for reasoning models
Date: 2026-05-20
Author: Liu Mingran
"""

from typing import Optional, Union

from sysai_framework.llms.base.utils import get_secret_str
from sysai_framework.llms.openai_like.chat.transformation import OpenAILikeChatConfig


class VolcEngineChatConfig(OpenAILikeChatConfig):
    """
    Volcengine (ByteDance/豆包) chat configuration.

    Reference: https://www.volcengine.com/docs/82379/1494384

    Supports thinking parameter for reasoning models.
    API Base: https://ark.cn-beijing.volces.com
    """

    frequency_penalty: Optional[int] = None
    function_call: Optional[Union[str, dict]] = None
    functions: Optional[list] = None
    logit_bias: Optional[dict] = None
    max_tokens: Optional[int] = None
    n: Optional[int] = None
    presence_penalty: Optional[int] = None
    stop: Optional[Union[str, list]] = None
    temperature: Optional[int] = None
    top_p: Optional[int] = None
    response_format: Optional[dict] = None

    def __init__(
        self,
        frequency_penalty: Optional[int] = None,
        function_call: Optional[Union[str, dict]] = None,
        functions: Optional[list] = None,
        logit_bias: Optional[dict] = None,
        max_tokens: Optional[int] = None,
        n: Optional[int] = None,
        presence_penalty: Optional[int] = None,
        stop: Optional[Union[str, list]] = None,
        temperature: Optional[int] = None,
        top_p: Optional[int] = None,
        response_format: Optional[dict] = None,
    ) -> None:
        locals_ = locals().copy()
        for key, value in locals_.items():
            if key != "self" and value is not None:
                setattr(self.__class__, key, value)

    @classmethod
    def get_config(cls):
        return super().get_config()

    def _get_openai_compatible_provider_info(
        self, api_base: Optional[str], api_key: Optional[str]
    ) -> tuple[Optional[str], Optional[str]]:
        api_base = (
            api_base
            or get_secret_str("ARK_API_BASE")
            or get_secret_str("VOLCENGINE_API_BASE")
            or "https://ark.cn-beijing.volces.com"
        )  # type: ignore
        dynamic_api_key = (
            api_key
            or get_secret_str("ARK_API_KEY")
            or get_secret_str("VOLCENGINE_API_KEY")
        )
        return api_base, dynamic_api_key

    def get_supported_openai_params(self, model: str) -> list:
        return [
            "frequency_penalty",
            "logit_bias",
            "logprobs",
            "top_logprobs",
            "max_completion_tokens",
            "max_tokens",
            "n",
            "presence_penalty",
            "seed",
            "stop",
            "stream",
            "stream_options",
            "temperature",
            "top_p",
            "tools",
            "tool_choice",
            "function_call",
            "functions",
            "max_retries",
            "extra_headers",
            "thinking",
        ]

    def map_openai_params(
        self,
        non_default_params: dict,
        optional_params: dict,
        model: str,
        drop_params: bool,
        replace_max_completion_tokens_with_max_tokens: bool = True,
    ) -> dict:
        optional_params = super().map_openai_params(
            non_default_params,
            optional_params,
            model,
            drop_params,
            replace_max_completion_tokens_with_max_tokens,
        )

        if "thinking" in optional_params:
            """
            The `thinking` parameter of VolcEngine model has different default values.
            Reference: https://www.volcengine.com/docs/82379/1449737#0002
            """
            thinking_value = optional_params.pop("thinking")

            if (
                thinking_value is not None
                and isinstance(thinking_value, dict)
                and thinking_value.get("type", None)
                in ["enabled", "disabled", "auto"]
            ):
                optional_params.setdefault("extra_body", {})[
                    "thinking"
                ] = thinking_value
        return optional_params