"""
Copyright (C) 2025 CTyunOS. All Rights Reserved.
File: transformation.py
Desc: Base configuration and exception classes for LLM providers
Date: 2025-11-17
Author: Liu Mingran
"""

import types
from abc import ABC
from typing import Optional, Union

import httpx

from .types import BaseLLMModelInfo


class BaseLLMException(Exception):
    """
    Base exception class for LLM provider errors.
    Provides Chat Completion API compatible error format.
    """

    def __init__(
        self,
        status_code: int,
        message: str,
        headers: Optional[Union[dict, httpx.Headers]] = None,
        request: Optional[httpx.Request] = None,
        response: Optional[httpx.Response] = None,
        body: Optional[dict] = None,
    ):
        self.status_code = status_code
        self.message: str = message
        self.headers = headers

        if request:
            self.request = request
        else:
            self.request = httpx.Request(
                method="POST", url="https://github.com/CTyunOS/SysAIFrame"
            )

        if response:
            self.response = response
        else:
            self.response = httpx.Response(
                status_code=status_code, request=self.request
            )

        self.body = body
        super().__init__(self.message)


class BaseConfig(ABC):
    """
    Base configuration class for all LLM providers.

    Subclasses should override:
    - get_supported_openai_params(model): Return list of supported Chat Completion API params
    - map_openai_params(...): Map Chat Completion API params to provider-specific format
    - get_complete_url(...): Construct complete API endpoint URL
    - _get_openai_compatible_provider_info(...): Get provider's api_base and api_key defaults
    """

    def __init__(self):
        pass
