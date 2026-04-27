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

# Type stubs for LiteLLM types
ChatCompletionMessageToolCall = dict
Choices = dict
Function = dict
Message = dict
ModelResponse = dict
ModelResponseStream = dict

def convert_to_model_response_object(*args, **kwargs):
    """Stub for convert_to_model_response_object"""
    return {}

# OpenAIError can use BaseLLMException from base module
from sysai_framework.llms.base.transformation import BaseLLMException as OpenAIError

if TYPE_CHECKING:
    from litellm.litellm_core_utils.litellm_logging import Logging as _LiteLLMLoggingObj
    from sysai_framework.llms.base.types import ChatCompletionToolParam

    LiteLLMLoggingObj = _LiteLLMLoggingObj
else:
    LiteLLMLoggingObj = Any


class OpenAIGPTConfig(BaseLLMModelInfo, BaseConfig):
    """
    Reference: https://platform.openai.com/docs/api-reference/chat/create
    (Chat Completion API specification reference)

    The class `OpenAIConfig` provides configuration for the Chat Completion API interface.
    """

    # Add a class variable to track if this is the base class
    _is_base_class = True

    frequency_penalty: Optional[int] = None
    function_call: Optional[Union[str, dict]] = None
    functions: Optional[list] = None
    logit_bias: Optional[dict] = None
    max_tokens: Optional[int] = None
    n: Optional[int] = None
    presence_penalty: Optional[int] = None
    stop: Optional[Union[str, list]] = None
    temperature: Optional[int] = None
    top_p: Optional[int] = None
    response_format: Optional[dict] = None

    def __init__(
        self,
        frequency_penalty: Optional[int] = None,
        function_call: Optional[Union[str, dict]] = None,
        functions: Optional[list] = None,
        logit_bias: Optional[dict] = None,
        max_tokens: Optional[int] = None,
        n: Optional[int] = None,
        presence_penalty: Optional[int] = None,
        stop: Optional[Union[str, list]] = None,
        temperature: Optional[int] = None,
        top_p: Optional[int] = None,
        response_format: Optional[dict] = None,
    ) -> None:
        locals_ = locals().copy()
        for key, value in locals_.items():
            if key != "self" and value is not None:
                setattr(self.__class__, key, value)

        self.__class__._is_base_class = False

    @classmethod
    def get_config(cls):
        return super().get_config()
