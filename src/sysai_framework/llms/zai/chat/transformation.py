"""
Copyright (C) 2026 CTyunOS. All Rights Reserved.
File: transformation.py
Desc: ZAI (智谱AI/GLM) chat completion transformation
      Based on litellm.llms.zai.chat.transformation
      Support for cache_control and thinking parameter
Date: 2026-05-20
Author: Liu Mingran
"""

from typing import List, Optional, Tuple

from sysai_framework.llms.base.utils import get_secret_str, supports_reasoning
from sysai_framework.llms.base.types import AllMessageValues, ChatCompletionToolParam
from sysai_framework.llms.openai.chat.gpt_transformation import OpenAIGPTConfig

ZAI_API_BASE = "https://api.z.ai/api/paas/v4"


class ZAIChatConfig(OpenAIGPTConfig):
    """
    ZAI (智谱AI/GLM) chat configuration.

    Supports:
    - cache_control (preserved in messages/tools)
    - thinking parameter for reasoning models (GLM-Z1)

    API Base: https://api.z.ai/api/paas/v4
    """

    @property
    def custom_llm_provider(self) -> Optional[str]:
        return "zai"

    def _get_openai_compatible_provider_info(
        self, api_base: Optional[str], api_key: Optional[str]
    ) -> Tuple[Optional[str], Optional[str]]:
        api_base = api_base or get_secret_str("ZAI_API_BASE") or ZAI_API_BASE
        dynamic_api_key = api_key or get_secret_str("ZAI_API_KEY")
        return api_base, dynamic_api_key

    def remove_cache_control_flag_from_messages_and_tools(
        self,
        model: str,
        messages: List[AllMessageValues],
        tools: Optional[List[ChatCompletionToolParam]] = None,
    ) -> Tuple[List[AllMessageValues], Optional[List[ChatCompletionToolParam]]]:
        """
        Override to preserve cache_control for GLM/ZAI.
        GLM supports cache_control - don't strip it.
        """
        return messages, tools

    def get_supported_openai_params(self, model: str) -> list:
        base_params = [
            "max_tokens",
            "stream",
            "stream_options",
            "temperature",
            "top_p",
            "stop",
            "tools",
            "tool_choice",
        ]

        # Add thinking parameter if model supports reasoning
        if supports_reasoning(model=model, custom_llm_provider=self.custom_llm_provider):
            base_params.append("thinking")

        return base_params