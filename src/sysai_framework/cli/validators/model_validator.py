"""
Copyright (C) 2025 CTyunOS. All Rights Reserved.
File: cli/validators/model_validator.py
Desc: Model parameter validation for CLI commands
Date: 2025-11-27
Author: Liu Mingran
"""

import re
from typing import Dict, Any, List, Optional, Tuple
from urllib.parse import urlparse


class ModelValidator:
    """
    Validates model configuration parameters

    Validation rules:
    - name: required, non-empty string, valid characters
    - api: required, valid URL format
    - api_key: required for cloud providers, optional for local (ollama)
    - provider: must be one of supported providers
    - priority: positive integer
    - timeout/max_retries: positive integers
    - capabilities: list of valid capability names
    """

    # Supported providers
    SUPPORTED_PROVIDERS = [
        'openai', 'openai_like', 'deepseek', 'dashscope',
        'moonshot', 'ollama', 'azure'
    ]

    # Local providers that don't require API key
    LOCAL_PROVIDERS = ['ollama']

    # Valid name pattern (alphanumeric, hyphens, underscores, periods, slashes)
    NAME_PATTERN = re.compile(r'^[a-zA-Z][a-zA-Z0-9_./-]*$')

    # Valid instance_id pattern
    INSTANCE_ID_PATTERN = re.compile(r'^[a-zA-Z0-9_-]+$')

    def __init__(self):
        self.errors: List[str] = []
        self.warnings: List[str] = []
