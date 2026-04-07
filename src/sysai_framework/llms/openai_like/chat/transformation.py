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
    """
    pass
