"""
Support for gpt model family
"""

from typing import (
    TYPE_CHECKING,
    Any,
    AsyncIterator,
    Coroutine,
    Iterator,
    List,
    Literal,
    Optional,
    Tuple,
    Union,
    cast,
    overload,
)

import httpx

# import litellm  # Disabled for SysAIFrame

# Stub implementations for LiteLLM imports
def _extract_reasoning_content(*args, **kwargs):
    """Stub for _extract_reasoning_content"""
    return None

def _handle_invalid_parallel_tool_calls(*args, **kwargs):
    """Stub for _handle_invalid_parallel_tool_calls"""
    return None

def _should_convert_tool_call_to_json_mode(*args, **kwargs):
    """Stub for _should_convert_tool_call_to_json_mode"""
    return False

def convert_url_to_base64(url: str) -> str:
    """Stub for convert_url_to_base64"""
    return ""

async def async_convert_url_to_base64(url: str) -> str:
    """Stub for async_convert_url_to_base64"""
    return ""

class BaseModelResponseIterator:
    """Stub for BaseModelResponseIterator"""
    pass

from sysai_framework.llms.base.utils import get_tool_call_names
from sysai_framework.llms.base.types import BaseLLMModelInfo
from sysai_framework.llms.base.transformation import BaseConfig, BaseLLMException
from sysai_framework.llms.base.utils import get_secret_str
from sysai_framework.llms.base.types import (
    AllMessageValues,
    ChatCompletionFileObject,
    ChatCompletionFileObjectFile,
    ChatCompletionImageObject,
    ChatCompletionImageUrlObject,
    OpenAIChatCompletionChoices,
    OpenAIMessageContentListBlock,
)
