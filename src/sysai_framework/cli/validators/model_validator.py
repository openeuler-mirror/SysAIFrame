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

    def _is_localhost(self, netloc: str) -> bool:
        """Check if host is localhost"""
        host = netloc.split(':')[0].lower()
        return host in ('localhost', '127.0.0.1', '::1')

    def _validate_api_key(self, api_key: Optional[str], provider: str) -> None:
        """Validate API key (required for cloud providers)"""
        is_local = provider.lower() in self.LOCAL_PROVIDERS

        if not api_key or api_key.strip() == '':
            if not is_local:
                self.errors.append(
                    f"API key (--api_key) is required for provider '{provider}'. "
                    f"Only local providers ({', '.join(self.LOCAL_PROVIDERS)}) can omit API key."
                )
        else:
            api_key = api_key.strip()

            # Warn about common placeholder keys
            placeholder_patterns = ['your-api-key', 'sk-xxx', 'api-key-here', 'placeholder']
            for pattern in placeholder_patterns:
                if pattern.lower() in api_key.lower():
                    self.warnings.append(
                        f"API key appears to be a placeholder. "
                        f"Please provide a valid API key."
                    )
                    break

            # Warn about mock key
            if api_key == 'sk-mock-key':
                self.warnings.append(
                    "Using mock API key 'sk-mock-key'. "
                    "This will cause authentication errors with real API endpoints."
                )

    def _validate_provider(self, provider: Optional[str]) -> None:
        """Validate provider type"""
        if not provider:
            return

        if not isinstance(provider, str):
            self.errors.append(f"Provider must be a string, got {type(provider).__name__}")
            return

        provider = provider.strip().lower()

        if provider not in [p.lower() for p in self.SUPPORTED_PROVIDERS]:
            self.errors.append(
                f"Unsupported provider '{provider}'. "
                f"Supported providers: {', '.join(self.SUPPORTED_PROVIDERS)}"
            )

    def _validate_instance_id(self, instance_id: str) -> None:
        """Validate instance ID format"""
        if not isinstance(instance_id, str):
            self.errors.append(f"Instance ID must be a string, got {type(instance_id).__name__}")
            return

        instance_id = instance_id.strip()

        if not instance_id:
            return

        if len(instance_id) > 64:
            self.errors.append("Instance ID is too long (max 64 characters)")
            return

        if not self.INSTANCE_ID_PATTERN.match(instance_id):
            self.errors.append(
                "Instance ID must contain only alphanumeric characters, "
                "hyphens, and underscores"
            )

    def _validate_priority(self, priority: Any) -> None:
        """Validate priority value"""
        if priority is None:
            return

        if not isinstance(priority, int):
            self.errors.append(f"Priority must be an integer, got {type(priority).__name__}")
            return

        if priority < 1:
            self.errors.append("Priority must be a positive integer (>= 1)")

        if priority > 100:
            self.errors.append("Priority must be <= 100")

    def _validate_timeout(self, timeout: Any) -> None:
        """Validate timeout value"""
        if timeout is None:
            return

        if not isinstance(timeout, int):
            self.errors.append(f"Timeout must be an integer, got {type(timeout).__name__}")
            return

        if timeout < 1:
            self.errors.append("Timeout must be a positive integer (>= 1)")

        if timeout > 3600:
            self.errors.append("Timeout must be <= 3600 seconds (1 hour)")

    def _validate_max_retries(self, max_retries: Any) -> None:
        """Validate max_retries value"""
        if max_retries is None:
            return

        if not isinstance(max_retries, int):
            self.errors.append(f"Max retries must be an integer, got {type(max_retries).__name__}")
            return

        if max_retries < 0:
            self.errors.append("Max retries must be a non-negative integer (>= 0)")

        if max_retries > 10:
            self.errors.append("Max retries must be <= 10")

    def _validate_capabilities(self, capabilities: Any) -> None:
        """Validate capabilities list"""
        if capabilities is None:
            return

        if isinstance(capabilities, str):
            return

        if not isinstance(capabilities, list):
            self.errors.append(
                f"Capabilities must be a list or comma-separated string, "
                f"got {type(capabilities).__name__}"
            )
            return

        for cap in capabilities:
            if not isinstance(cap, str):
                self.errors.append(f"Each capability must be a string, got {type(cap).__name__}")
            elif not cap.strip():
                self.errors.append("Capability name cannot be empty")

    @staticmethod
    def parse_capabilities(capabilities_str: Optional[str]) -> List[str]:
        """Parse comma-separated capabilities string into list"""
        if not capabilities_str:
            return ['general']

        return [cap.strip() for cap in capabilities_str.split(',') if cap.strip()]

    @staticmethod
    def normalize_model_data(data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize and set defaults for model data

        Args:
            data: Raw model data from CLI

        Returns:
            Normalized model data with defaults
        """
        normalized = {}

        normalized['name'] = data.get('name', '').strip()
        normalized['api_base'] = data.get('api_base', '').strip()
        normalized['provider'] = data.get('provider', 'openai_like').strip().lower()
        normalized['priority'] = data.get('priority', 1)
        normalized['timeout'] = data.get('timeout', 30)
        normalized['max_retries'] = data.get('max_retries', 3)
        normalized['supports_streaming'] = data.get('supports_streaming', True)
        normalized['is_healthy'] = True

        if data.get('api_key'):
            normalized['api_key'] = data['api_key'].strip()

        if data.get('instance_id'):
            normalized['instance_id'] = data['instance_id'].strip()

        if data.get('capabilities'):
            normalized['capabilities'] = data['capabilities']

        if data.get('endpoint'):
            normalized['endpoint'] = data['endpoint'].strip()

        return normalized
