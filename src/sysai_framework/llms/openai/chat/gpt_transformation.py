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

    def transform_request(
        self,
        model: str,
        messages: List[AllMessageValues],
        optional_params: dict,
        litellm_params: dict,
        headers: dict,
    ) -> dict:
        """
        Transform the overall request to be sent to the API.
        """
        messages = self._transform_messages(messages=messages, model=model)
        messages, tools = self.remove_cache_control_flag_from_messages_and_tools(
            model=model, messages=messages, tools=optional_params.get("tools", [])
        )
        if tools is not None and len(tools) > 0:
            optional_params["tools"] = tools

        optional_params.pop("max_retries", None)

        return {
            "model": model,
            "messages": messages,
            **optional_params,
        }

    async def async_transform_request(
        self,
        model: str,
        messages: List[AllMessageValues],
        optional_params: dict,
        litellm_params: dict,
        headers: dict,
    ) -> dict:
        transformed_messages = await self._transform_messages(
            messages=messages, model=model, is_async=True
        )
        transformed_messages, tools = (
            self.remove_cache_control_flag_from_messages_and_tools(
                model=model,
                messages=transformed_messages,
                tools=optional_params.get("tools", []),
            )
        )
        if tools is not None and len(tools) > 0:
            optional_params["tools"] = tools
        if self.__class__._is_base_class:
            return {
                "model": model,
                "messages": transformed_messages,
                **optional_params,
            }
        else:
            return self.transform_request(
                model, messages, optional_params, litellm_params, headers
            )

    def _passed_in_tools(self, optional_params: dict) -> bool:
        return optional_params.get("tools", None) is not None

    def _check_and_fix_if_content_is_tool_call(
        self, content: str, optional_params: dict
    ) -> Optional[ChatCompletionMessageToolCall]:
        """
        Check if the content is a tool call
        """
        import json

        if not self._passed_in_tools(optional_params):
            return None
        tool_call_names = get_tool_call_names(optional_params.get("tools", []))
        try:
            json_content = json.loads(content)
            if (
                json_content.get("type") == "function"
                and json_content.get("name") in tool_call_names
            ):
                return ChatCompletionMessageToolCall(
                    function=Function(
                        name=json_content.get("name"),
                        arguments=json_content.get("arguments"),
                    )
                )
        except Exception:
            return None

        return None

    def _get_finish_reason(self, message: Message, received_finish_reason: str) -> str:
        if message.tool_calls is not None:
            return "tool_calls"
        else:
            return received_finish_reason

    def _transform_choices(
        self,
        choices: List[OpenAIChatCompletionChoices],
        json_mode: Optional[bool] = None,
        optional_params: Optional[dict] = None,
    ) -> List[Choices]:
        transformed_choices = []

        for choice in choices:
            tool_calls = choice["message"].get("tool_calls", None)
            new_tool_calls: Optional[List[ChatCompletionMessageToolCall]] = None
            message_content = choice["message"].get("content", None)
            if tool_calls is not None:
                _openai_tool_calls = []
                for _tc in tool_calls:
                    _openai_tc = ChatCompletionMessageToolCall(**_tc)
                    _openai_tool_calls.append(_openai_tc)
                fixed_tool_calls = _handle_invalid_parallel_tool_calls(
                    _openai_tool_calls
                )

                if fixed_tool_calls is not None:
                    new_tool_calls = fixed_tool_calls
            elif (
                optional_params is not None
                and message_content
                and isinstance(message_content, str)
            ):
                new_tool_call = self._check_and_fix_if_content_is_tool_call(
                    message_content, optional_params
                )
                if new_tool_call is not None:
                    choice["message"]["content"] = None
                    new_tool_calls = [new_tool_call]

            translated_message: Optional[Message] = None
            finish_reason: Optional[str] = None
            if new_tool_calls and _should_convert_tool_call_to_json_mode(
                tool_calls=new_tool_calls,
                convert_tool_call_to_json_mode=json_mode,
            ):
                json_mode_content_str: Optional[str] = (
                    str(new_tool_calls[0]["function"].get("arguments", "")) or None
                )
                if json_mode_content_str is not None:
                    translated_message = Message(content=json_mode_content_str)
                    finish_reason = "stop"

            if translated_message is None:
                (
                    reasoning_content,
                    content_str,
                ) = _extract_reasoning_content(cast(dict, choice["message"]))

                translated_message = Message(
                    role="assistant",
                    content=content_str,
                    reasoning_content=reasoning_content,
                    thinking_blocks=None,
                    tool_calls=new_tool_calls,
                )

            if finish_reason is None:
                finish_reason = choice["finish_reason"]

            translated_choice = Choices(
                finish_reason=finish_reason,
                index=choice["index"],
                message=translated_message,
                logprobs=None,
                enhancements=None,
            )

            translated_choice.finish_reason = self._get_finish_reason(
                translated_message, choice["finish_reason"]
            )
            transformed_choices.append(translated_choice)

        return transformed_choices

    def transform_response(
        self,
        model: str,
        raw_response: httpx.Response,
        model_response: ModelResponse,
        logging_obj: LiteLLMLoggingObj,
        request_data: dict,
        messages: List[AllMessageValues],
        optional_params: dict,
        litellm_params: dict,
        encoding: Any,
        api_key: Optional[str] = None,
        json_mode: Optional[bool] = None,
    ) -> ModelResponse:
        """
        Transform the response from the API.
        """
        logging_obj.post_call(
            input=messages,
            api_key=api_key,
            original_response=raw_response.text,
            additional_args={"complete_input_dict": request_data},
        )

        try:
            completion_response = raw_response.json()
        except Exception as e:
            response_headers = getattr(raw_response, "headers", None)
            raise OpenAIError(
                message="Unable to get json response - {}, Original Response: {}".format(
                    str(e), raw_response.text
                ),
                status_code=raw_response.status_code,
                headers=response_headers,
            )
        raw_response_headers = dict(raw_response.headers)
        final_response_obj = convert_to_model_response_object(
            response_object=completion_response,
            model_response_object=model_response,
            hidden_params={"headers": raw_response_headers},
            _response_headers=raw_response_headers,
        )

        return cast(ModelResponse, final_response_obj)

    def get_error_class(
        self, error_message: str, status_code: int, headers: Union[dict, httpx.Headers]
    ) -> BaseLLMException:
        return OpenAIError(
            status_code=status_code,
            message=error_message,
            headers=cast(httpx.Headers, headers),
        )
