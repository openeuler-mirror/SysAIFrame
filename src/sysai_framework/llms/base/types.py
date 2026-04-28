"""
Copyright (C) 2025 CTyunOS. All Rights Reserved.
File: types.py
Desc: Type definitions for LLM provider compatibility
Date: 2025-11-17
Author: Liu Mingran
"""

from typing import Any, Dict

# Type aliases for Chat Completion API message types
AllMessageValues = Dict[str, Any]
ChatCompletionFileObject = Dict[str, Any]
ChatCompletionFileObjectFile = Dict[str, Any]
ChatCompletionImageObject = Dict[str, Any]
ChatCompletionImageUrlObject = Dict[str, Any]
OpenAIChatCompletionChoices = Dict[str, Any]
OpenAIMessageContentListBlock = Dict[str, Any]
ChatCompletionToolParam = Dict[str, Any]


# Base class for provider compatibility
class BaseLLMModelInfo:
    """
    Base class for LLM model information

    Provides a common base for provider-specific model info classes.
    Subclasses can add provider-specific attributes as needed.
    """
    pass

