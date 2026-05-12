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

    def validate(self, model_data: Dict[str, Any]) -> Tuple[bool, List[str], List[str]]:
        """
        Validate model configuration

        Args:
            model_data: Model configuration dictionary

        Returns:
            (is_valid, errors, warnings)
        """
        self.errors = []
        self.warnings = []

        # Validate required fields
        if not model_data.get('name'):
            self.errors.append("'name' is required")

        if not model_data.get('api_key') and not model_data.get('api_base'):
            # Check if it's a local provider
            provider = model_data.get('provider', '').lower()
            if provider not in self.LOCAL_PROVIDERS:
                self.errors.append("'api_key' or 'api_base' is required")

        # Validate name format
        if model_data.get('name'):
            name = model_data['name']
            if not self.NAME_PATTERN.match(name):
                self.errors.append(
                    f"Invalid name '{name}': must start with letter and contain only "
                    f"alphanumeric, underscore, hyphen, period, or slash characters"
                )

        # Validate provider
        provider = model_data.get('provider', '').lower()
        if provider and provider not in self.SUPPORTED_PROVIDERS:
            self.errors.append(
                f"Unsupported provider '{provider}': "
                f"must be one of {', '.join(self.SUPPORTED_PROVIDERS)}"
            )

        # Validate URL if api_base provided
        api_base = model_data.get('api_base')
        if api_base:
            if not self._is_valid_url(api_base):
                self.errors.append(f"Invalid API URL: {api_base}")

        # Validate priority
        priority = model_data.get('priority')
        if priority is not None:
            if not isinstance(priority, int) or priority < 1:
                self.errors.append(f"Invalid priority '{priority}': must be positive integer")

        # Validate timeout
        timeout = model_data.get('timeout')
        if timeout is not None:
            if not isinstance(timeout, (int, float)) or timeout <= 0:
                self.errors.append(f"Invalid timeout '{timeout}': must be positive number")

        # Validate max_retries
        max_retries = model_data.get('max_retries')
        if max_retries is not None:
            if not isinstance(max_retries, int) or max_retries < 0:
                self.errors.append(f"Invalid max_retries '{max_retries}': must be non-negative integer")

        # Validate capabilities
        capabilities = model_data.get('capabilities')
        if capabilities is not None:
            if not isinstance(capabilities, list):
                self.errors.append(f"'capabilities' must be a list")
            else:
                for cap in capabilities:
                    if not isinstance(cap, str):
                        self.errors.append(f"Invalid capability '{cap}': must be string")
                        break

        # Warnings for non-critical issues
        if not model_data.get('capabilities'):
            self.warnings.append("No capabilities specified, defaults will be used")

        if not api_base and not model_data.get('endpoint'):
            self.warnings.append("No API endpoint specified")

        return (len(self.errors) == 0, self.errors, self.warnings)

    def _is_valid_url(self, url: str) -> bool:
        """Check if URL is valid"""
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc])
        except Exception:
            return False
