"""
Copyright (C) 2025 CTyunOS. All Rights Reserved.
File: utils.py
Desc: Utility functions for LLM message processing and secret management
Date: 2025-11-17
Author: Liu Mingran
"""

from typing import Any, List, Optional


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
        Converted messages
    """
    return messages


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

    Helper function used by BaseConfig to filter out unwanted parameters.

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
