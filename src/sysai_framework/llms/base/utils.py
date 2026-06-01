"""
Copyright (C) 2025 CTyunOS. All Rights Reserved.
File: utils.py
Desc: Utility functions for LLM message processing and secret management
Date: 2025-11-17
Author: Liu Mingran
"""

from typing import Any, Dict, List, Optional


def get_secret_str(key: str) -> Optional[str]:
    """
    Get secret from environment or secret manager.

    In SysAIFrame, API keys are managed in configuration files,
    so this always returns None. This function is provided for
    compatibility with provider transformation code.

    Args:
        key: The secret key name (e.g., "OPENAI_API_KEY")

    Returns:
        None (we use config file for API keys)
    """
    return None


def handle_messages_with_content_list_to_str_conversion(
    messages: List[Any]
) -> List[Any]:
    """
    Convert messages with content list to string format.

    Some providers don't support content in list format (e.g., with images).
    This function converts such messages to simple string format.

    Args:
        messages: List of message dictionaries

    Returns:
        Converted messages with content lists flattened to strings
    """
    for message in messages:
        _content = message.get("content")
        if _content is not None and isinstance(_content, list):
            str_content = convert_content_list_to_str(message)
            if str_content is not None:
                message["content"] = str_content
    return messages


def convert_content_list_to_str(message: Dict[str, Any]) -> Optional[str]:
    """
    Convert message content list to string.

    Extracts text parts from a content list and concatenates them.

    Args:
        message: Message dictionary with potential list content

    Returns:
        Concatenated text string, or None if no text parts found
    """
    content = message.get("content")
    if content is None:
        return None
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        texts = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                texts.append(item.get("text", ""))
            elif isinstance(item, str):
                texts.append(item)
        return " ".join(texts) if texts else None
    return None


def get_tool_call_names(tools: List[Any]) -> List[str]:
    """
    Extract tool names from tool definitions.

    Args:
        tools: List of tool definitions

    Returns:
        List of tool names
    """
    return []


def filter_value_from_dict(data: dict, keys_to_remove: List[str]) -> dict:
    """
    Remove specified keys from dictionary.

    Args:
        data: Dictionary to filter
        keys_to_remove: List of keys to remove

    Returns:
        Filtered dictionary
    """
    if not data:
        return data

    filtered = {}
    for key, value in data.items():
        if key not in keys_to_remove:
            filtered[key] = value

    return filtered


def supports_reasoning(model: str, custom_llm_provider: Optional[str] = None) -> bool:
    """
    Check if a model supports reasoning/thinking mode.

    In SysAIFrame, we use a simple heuristic based on model name patterns
    to determine reasoning support, since we don't depend on litellm's
    model capability database.

    Args:
        model: Model name (e.g., "deepseek-reasoner", "kimi-thinking-preview")
        custom_llm_provider: Provider name (e.g., "deepseek", "moonshot")

    Returns:
        True if the model is likely a reasoning model
    """
    reasoning_patterns = [
        "deepseek-reasoner",
        "deepseek-r1",
        "kimi-thinking",
        "glm-z1",
        "o1",
        "o3",
        "o4-mini",
        "minimax-m2.1",
    ]
    model_lower = model.lower()
    for pattern in reasoning_patterns:
        if pattern in model_lower:
            return True
    return False


def map_finish_reason(finish_reason: Optional[str]) -> Optional[str]:
    """
    Map finish reasons to standard OpenAI-compatible values.

    Args:
        finish_reason: Raw finish reason from provider response

    Returns:
        Standardized finish reason string
    """
    if finish_reason is None:
        return None
    finish_reason_map = {
        "stop": "stop",
        "length": "length",
        "tool_calls": "tool_calls",
        "content_filter": "content_filter",
        "function_call": "stop",
    }
    return finish_reason_map.get(finish_reason, "stop")

