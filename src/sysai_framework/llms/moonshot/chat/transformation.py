"""
Translates from Chat Completion API `/v1/chat/completions` to Moonshot AI's `/v1/chat/completions`
"""

from typing import Any, Coroutine, List, Literal, Optional, Tuple, Union, overload

from sysai_framework.llms.base.utils import (
    handle_messages_with_content_list_to_str_conversion,
)
from sysai_framework.llms.base.utils import get_secret_str
from sysai_framework.llms.base.types import AllMessageValues

from ...openai.chat.gpt_transformation import OpenAIGPTConfig
