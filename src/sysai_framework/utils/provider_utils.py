"""
Copyright (C) 2025 CTyunOS. All Rights Reserved.
File: provider_utils.py
Desc: Provider detection and routing utilities
Date: 2025-11-17
Author: Liu Mingran
"""

import logging
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


# Provider list - supported providers (single source of truth)
SUPPORTED_PROVIDERS = [
    "dashscope",
    "moonshot",
    "volcengine",
    "deepseek",
    "openai",
    "openai_like",
    "ollama",
    "azure",
    "zai",
    "minimax",
]

# Chat Completion API compatible endpoints mapping
OPENAI_COMPATIBLE_ENDPOINTS = {
    "dashscope.aliyuncs.com": "dashscope",
    "dashscope-intl.aliyuncs.com": "dashscope",
    "api.moonshot.cn": "moonshot",
    "api.moonshot.ai": "moonshot",
    "ark.cn-beijing.volces.com": "volcengine",
    "api.deepseek.com": "deepseek",
    "api.z.ai": "zai",
    "api.minimax.io": "minimax",
    "api.minimaxi.com": "minimax",
}


def get_llm_provider(
    model: str,
    custom_llm_provider: Optional[str] = None,
    api_base: Optional[str] = None,
    api_key: Optional[str] = None,
) -> Tuple[str, str, Optional[str], Optional[str]]:
    """
    Returns the provider for a given model name.

    Logic:
    1. If custom_llm_provider is explicitly set, use it
    2. Check if model has provider prefix (e.g., 'dashscope/qwen-turbo')
    3. Check if api_base matches known provider endpoints
    4. Default to 'openai_like'

    Args:
        model: Model name (may include provider prefix)
        custom_llm_provider: Explicitly specified provider
        api_base: API base URL
        api_key: API key

    Returns:
        Tuple of (model, custom_llm_provider, api_key, api_base)

    Examples:
        >>> get_llm_provider("dashscope/qwen-turbo")
        ('qwen-turbo', 'dashscope', None, None)

        >>> get_llm_provider("qwen-turbo", custom_llm_provider="dashscope")
        ('qwen-turbo', 'dashscope', None, None)

        >>> get_llm_provider("model", api_base="https://dashscope.aliyuncs.com/v1")
        ('model', 'dashscope', None, 'https://dashscope.aliyuncs.com/v1')
    """

    # Priority 1: If custom_llm_provider is explicitly set
    if custom_llm_provider and custom_llm_provider in SUPPORTED_PROVIDERS:
        logger.debug(f"Using explicitly set provider: {custom_llm_provider}")
        return model, custom_llm_provider, api_key, api_base

    # Priority 2: Check if model has provider prefix
    if "/" in model:
        parts = model.split("/", 1)
        potential_provider = parts[0]

        if potential_provider in SUPPORTED_PROVIDERS:
            actual_model = parts[1]
            logger.debug(
                f"Detected provider '{potential_provider}' from model prefix, "
                f"actual model: '{actual_model}'"
            )
            return actual_model, potential_provider, api_key, api_base

    # Priority 3: Check if api_base matches known endpoints
    if api_base:
        for endpoint, provider in OPENAI_COMPATIBLE_ENDPOINTS.items():
            if endpoint in api_base:
                logger.debug(
                    f"Detected provider '{provider}' from api_base: {api_base}"
                )
                return model, provider, api_key, api_base

    # Default: openai_like for generic Chat Completion API compatible providers
    logger.debug(f"No specific provider detected, using 'openai_like' for model: {model}")
    return model, "openai_like", api_key, api_base


def get_provider_default_api_base(provider: str) -> Optional[str]:
    """
    Get the default API base URL for a provider.

    Args:
        provider: Provider name

    Returns:
        Default API base URL or None
    """
    defaults = {
        "dashscope": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "moonshot": "https://api.moonshot.cn/v1",
        "deepseek": "https://api.deepseek.com/beta",
        "openai": "https://api.openai.com/v1",
        "volcengine": "https://ark.cn-beijing.volces.com",
        "zai": "https://api.z.ai/api/paas/v4",
        "minimax": "https://api.minimaxi.com/v1",
    }

    return defaults.get(provider)
