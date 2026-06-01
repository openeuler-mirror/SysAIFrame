"""
Copyright (C) 2026 CTyunOS. All Rights Reserved.
File: transformation.py
Desc: MiniMax (海螺AI) chat completion transformation
      Based on litellm.llms.minimax.chat.transformation
      Support for cache_control, reasoning_split, and thinking parameter
Date: 2026-05-20
Author: Liu Mingran
"""

from typing import List, Optional, Tuple

from sysai_framework.llms.base.utils import get_secret_str, supports_reasoning
from sysai_framework.llms.base.types import AllMessageValues, ChatCompletionToolParam
from sysai_framework.llms.openai.chat.gpt_transformation import OpenAIGPTConfig


class MinimaxChatConfig(OpenAIGPTConfig):
    """
    MiniMax (海螺AI) chat configuration.

    MiniMax provides a Chat Completion API compatible interface at:
    - International: https://api.minimax.io/v1
    - China: https://api.minimaxi.com/v1

    Supports:
    - cache_control (preserved in messages/tools)
    - reasoning_split parameter
    - thinking parameter for reasoning models

    Supported models:
    - MiniMax-M2.1
    - MiniMax-M2.1-lightning
    - MiniMax-M2
    """

    @staticmethod
    def get_api_key(api_key: Optional[str] = None) -> Optional[str]:
        """Get MiniMax API key from environment or parameters."""
        return api_key or get_secret_str("MINIMAX_API_KEY")

    @staticmethod
    def get_api_base(api_base: Optional[str] = None) -> str:
        """
        Get MiniMax API base URL.
        Defaults to China endpoint: https://api.minimaxi.com/v1
        """
        return (
            api_base
            or get_secret_str("MINIMAX_API_BASE")
            or "https://api.minimaxi.com/v1"  # China endpoint by default
        )

    def get_complete_url(
        self,
        api_base: Optional[str],
        api_key: Optional[str],
        model: str,
        optional_params: dict,
        litellm_params: dict,
        stream: Optional[bool] = None,
    ) -> str:
        """Get the complete URL for MiniMax API."""
        base_url = self.get_api_base(api_base=api_base)

        if base_url.endswith("/chat/completions"):
            return base_url
        elif base_url.endswith("/v1"):
            return f"{base_url}/chat/completions"
        elif base_url.endswith("/"):
            return f"{base_url}v1/chat/completions"
        else:
            return f"{base_url}/v1/chat/completions"

    def remove_cache_control_flag_from_messages_and_tools(
        self,
        model: str,
        messages: List[AllMessageValues],
        tools: Optional[List[ChatCompletionToolParam]] = None,
    ) -> Tuple[List[AllMessageValues], Optional[List[ChatCompletionToolParam]]]:
        """
        Override to preserve cache_control for MiniMax.
        MiniMax supports cache_control - don't strip it.
        """
        return messages, tools

    def get_supported_openai_params(self, model: str) -> list:
        """Get supported parameters for MiniMax."""
        base_params = super().get_supported_openai_params(model=model)
        additional_params = ["reasoning_split"]

        # Add thinking parameter if model supports reasoning
        if supports_reasoning(model=model, custom_llm_provider="minimax"):
            additional_params.append("thinking")

        return base_params + additional_params