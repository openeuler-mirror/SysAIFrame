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

    def get_supported_openai_params(self, model: str) -> list:
        base_params = [
            "frequency_penalty",
            "logit_bias",
            "logprobs",
            "top_logprobs",
            "max_tokens",
            "max_completion_tokens",
            "modalities",
            "prediction",
            "n",
            "presence_penalty",
            "seed",
            "stop",
            "stream",
            "stream_options",
            "temperature",
            "top_p",
            "tools",
            "tool_choice",
            "function_call",
            "functions",
            "max_retries",
            "extra_headers",
            "parallel_tool_calls",
            "audio",
            "web_search_options",
            "service_tier",
            "safety_identifier",
        ]

        model_specific_params = []
        if (
            model != "gpt-3.5-turbo-16k" and model != "gpt-4"
        ):
            model_specific_params.append("response_format")

        model_specific_params.append("user")
        return base_params + model_specific_params

    def _map_openai_params(
        self,
        non_default_params: dict,
        optional_params: dict,
        model: str,
        drop_params: bool,
    ) -> dict:
        """
        If any supported Chat Completion API params are in non_default_params, add them to optional_params
        """
        supported_openai_params = self.get_supported_openai_params(model)
        for param, value in non_default_params.items():
            if param in supported_openai_params:
                optional_params[param] = value
        return optional_params

    def map_openai_params(
        self,
        non_default_params: dict,
        optional_params: dict,
        model: str,
        drop_params: bool,
    ) -> dict:
        return self._map_openai_params(
            non_default_params=non_default_params,
            optional_params=optional_params,
            model=model,
            drop_params=drop_params,
        )

    def contains_pdf_url(self, content_item: ChatCompletionFileObjectFile) -> bool:
        potential_pdf_url_starts = ["https://", "http://", "www."]
        file_id = content_item.get("file_id")
        if file_id and any(
            file_id.startswith(start) for start in potential_pdf_url_starts
        ):
            return True
        return False

    def _handle_pdf_url(
        self, content_item: ChatCompletionFileObjectFile
    ) -> ChatCompletionFileObjectFile:
        content_copy = content_item.copy()
        file_id = content_copy.get("file_id")
        if file_id is not None:
            base64_data = convert_url_to_base64(file_id)
            content_copy["file_data"] = base64_data
            content_copy["filename"] = "my_file.pdf"
            content_copy.pop("file_id")
        return content_copy

    async def _async_handle_pdf_url(
        self, content_item: ChatCompletionFileObjectFile
    ) -> ChatCompletionFileObjectFile:
        file_id = content_item.get("file_id")
        if file_id is not None:
            base64_data = await async_convert_url_to_base64(file_id)
            content_item["file_data"] = base64_data
            content_item["filename"] = "my_file.pdf"
            content_item.pop("file_id")
        return content_item

    def _common_file_data_check(
        self, content_item: ChatCompletionFileObjectFile
    ) -> ChatCompletionFileObjectFile:
        file_data = content_item.get("file_data")
        filename = content_item.get("filename")
        if file_data is not None and filename is None:
            content_item["filename"] = "my_file.pdf"
        return content_item

    def _apply_common_transform_content_item(
        self,
        content_item: OpenAIMessageContentListBlock,
    ) -> OpenAIMessageContentListBlock:
        litellm_specific_params = {"format"}
        if content_item.get("type") == "image_url":
            content_item = cast(ChatCompletionImageObject, content_item)
            if isinstance(content_item["image_url"], str):
                content_item["image_url"] = {
                    "url": content_item["image_url"],
                }
            elif isinstance(content_item["image_url"], dict):
                new_image_url_obj = ChatCompletionImageUrlObject(
                    **{
                        k: v
                        for k, v in content_item["image_url"].items()
                        if k not in litellm_specific_params
                    }
                )
                content_item["image_url"] = new_image_url_obj
        elif content_item.get("type") == "file":
            content_item = cast(ChatCompletionFileObject, content_item)
            file_obj = content_item["file"]
            new_file_obj = ChatCompletionFileObjectFile(
                **{
                    k: v
                    for k, v in file_obj.items()
                    if k not in litellm_specific_params
                }
            )
            content_item["file"] = new_file_obj

        return content_item

    def _transform_content_item(
        self,
        content_item: OpenAIMessageContentListBlock,
    ) -> OpenAIMessageContentListBlock:
        content_item = self._apply_common_transform_content_item(content_item)
        content_item_type = content_item.get("type")
        potential_file_obj = content_item.get("file")
        if content_item_type == "file" and potential_file_obj:
            file_obj = cast(ChatCompletionFileObjectFile, potential_file_obj)
            content_item_typed = cast(ChatCompletionFileObject, content_item)
            if self.contains_pdf_url(file_obj):
                file_obj = self._handle_pdf_url(file_obj)
            file_obj = self._common_file_data_check(file_obj)
            content_item_typed["file"] = file_obj
            content_item = content_item_typed
        return content_item

    async def _async_transform_content_item(
        self, content_item: OpenAIMessageContentListBlock, is_async: bool = False
    ) -> OpenAIMessageContentListBlock:
        content_item = self._apply_common_transform_content_item(content_item)
        content_item_type = content_item.get("type")
        potential_file_obj = content_item.get("file")
        if content_item_type == "file" and potential_file_obj:
            file_obj = cast(ChatCompletionFileObjectFile, potential_file_obj)
            content_item_typed = cast(ChatCompletionFileObject, content_item)
            if self.contains_pdf_url(file_obj):
                file_obj = await self._async_handle_pdf_url(file_obj)
            file_obj = self._common_file_data_check(file_obj)
            content_item_typed["file"] = file_obj
            content_item = content_item_typed
        return content_item

    # fmt: off

    @overload
    def _transform_messages(
        self, messages: List[AllMessageValues], model: str, is_async: Literal[True]
    ) -> Coroutine[Any, Any, List[AllMessageValues]]:
        ...

    @overload
    def _transform_messages(
        self,
        messages: List[AllMessageValues],
        model: str,
        is_async: Literal[False] = False,
    ) -> List[AllMessageValues]:
        ...

    # fmt: on

    def _transform_messages(
        self, messages: List[AllMessageValues], model: str, is_async: bool = False
    ) -> Union[List[AllMessageValues], Coroutine[Any, Any, List[AllMessageValues]]]:
        """OpenAI no longer supports image_url as a string, so we need to convert it to a dict"""

        async def _async_transform():
            for message in messages:
                message_content = message.get("content")
                message_role = message.get("role")

                if (
                    message_role == "user"
                    and message_content
                    and isinstance(message_content, list)
                ):
                    message_content_types = cast(
                        List[OpenAIMessageContentListBlock], message_content
                    )
                    for i, content_item in enumerate(message_content_types):
                        message_content_types[i] = (
                            await self._async_transform_content_item(
                                cast(OpenAIMessageContentListBlock, content_item),
                            )
                        )
            return messages

        if is_async:
            return _async_transform()
        else:
            for message in messages:
                message_content = message.get("content")
                message_role = message.get("role")
                if (
                    message_role == "user"
                    and message_content
                    and isinstance(message_content, list)
                ):
                    message_content_types = cast(
                        List[OpenAIMessageContentListBlock], message_content
                    )
                    for i, content_item in enumerate(message_content):
                        message_content_types[i] = self._transform_content_item(
                            cast(OpenAIMessageContentListBlock, content_item)
                        )
            return messages

    def remove_cache_control_flag_from_messages_and_tools(
        self,
        model: str,
        messages: List[AllMessageValues],
        tools: Optional[List["ChatCompletionToolParam"]] = None,
    ) -> Tuple[List[AllMessageValues], Optional[List["ChatCompletionToolParam"]]]:
        from sysai_framework.llms.base.utils import (
            filter_value_from_dict,
        )
        from sysai_framework.llms.base.types import ChatCompletionToolParam

        for i, message in enumerate(messages):
            messages[i] = cast(
                AllMessageValues, filter_value_from_dict(message, "cache_control")
            )
        if tools is not None:
            for i, tool in enumerate(tools):
                tools[i] = cast(
                    ChatCompletionToolParam,
                    filter_value_from_dict(tool, "cache_control"),
                )
        return messages, tools
