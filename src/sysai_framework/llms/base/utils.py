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
