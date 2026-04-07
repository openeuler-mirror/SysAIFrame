"""
Copyright (C) 2025 CTyunOS. All Rights Reserved.
File: transformation.py
Desc: OpenAI-like provider configuration
      For generic Chat Completion API compatible endpoints
      Adapted from LiteLLM
Date: 2025-11-17
Author: Liu Mingran
"""

from typing import Optional, Tuple

from ...openai.chat.gpt_transformation import OpenAIGPTConfig


class OpenAILikeChatConfig(OpenAIGPTConfig):
    """
    Configuration for Chat Completion API compatible endpoints.

    This class is used for any provider that follows the Chat Completion API specification
    but is not one of the specifically supported providers.

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

        For OpenAI-like providers, we use whatever the user provides.
        No defaults are assumed since these are custom endpoints.

        Args:
            api_base: User-provided api_base (required)
            api_key: User-provided api_key (may be empty for some local providers)

        Returns:
            Tuple of (api_base, api_key)
        """
        # For Chat Completion API compatible providers, use what's provided
        # api_base must be provided, api_key can be empty string for local providers
        if not api_key:
            api_key = ""  # Some providers like vLLM don't require an API key

        return api_base, api_key

