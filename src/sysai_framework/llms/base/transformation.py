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
