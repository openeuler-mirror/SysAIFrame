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

from sysai_framework.utils.provider_utils import SUPPORTED_PROVIDERS


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
        self._validate_name(model_data.get('name'))
        self._validate_api(model_data.get('api_base'))
        
        # Validate provider and conditional api_key requirement
        provider = model_data.get('provider', 'openai_like')
        self._validate_provider(provider)
        self._validate_api_key(model_data.get('api_key'), provider)
        
        # Validate optional fields
        if 'instance_id' in model_data and model_data['instance_id']:
            self._validate_instance_id(model_data['instance_id'])
        
        if 'priority' in model_data:
            self._validate_priority(model_data['priority'])
        
        if 'timeout' in model_data:
            self._validate_timeout(model_data['timeout'])

        if 'stream_timeout' in model_data:
            self._validate_stream_timeout(model_data['stream_timeout'])

        if 'max_retries' in model_data:
            self._validate_max_retries(model_data['max_retries'])
        
        if 'capabilities' in model_data:
            self._validate_capabilities(model_data['capabilities'])
        
        is_valid = len(self.errors) == 0
        return is_valid, self.errors, self.warnings
    
    def _validate_name(self, name: Optional[str]) -> None:
        """Validate model name"""
        if not name:
            self.errors.append("Model name is required")
            return
        
        if not isinstance(name, str):
            self.errors.append(f"Model name must be a string, got {type(name).__name__}")
            return
        
        name = name.strip()
        if not name:
            self.errors.append("Model name cannot be empty")
            return
        
        if len(name) > 64:
            self.errors.append("Model name is too long (max 64 characters)")
            return
        
        if not self.NAME_PATTERN.match(name):
            self.errors.append(
                "Model name must start with a letter and contain only "
                "alphanumeric characters, hyphens, underscores, periods, and slashes"
            )
    
    def _validate_api(self, api: Optional[str]) -> None:
        """Validate API base URL"""
        if not api:
            self.errors.append("API URL (--api) is required")
            return
        
        if not isinstance(api, str):
            self.errors.append(f"API URL must be a string, got {type(api).__name__}")
            return
        
        api = api.strip()
        
        # Parse URL
        try:
            parsed = urlparse(api)
            
            if not parsed.scheme:
                self.errors.append("API URL must include scheme (http:// or https://)")
                return
            
            if parsed.scheme not in ('http', 'https'):
                self.errors.append(f"API URL scheme must be http or https, got '{parsed.scheme}'")
                return
            
            if not parsed.netloc:
                self.errors.append("API URL must include host")
                return
            
            # Warn about http in production
            if parsed.scheme == 'http' and not self._is_localhost(parsed.netloc):
                self.warnings.append(
                    "Using HTTP for non-localhost API may be insecure. "
                    "Consider using HTTPS."
                )
                
        except Exception as e:
            self.errors.append(f"Invalid API URL format: {e}")
    
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
            return  # Will use default
        
        if not isinstance(provider, str):
            self.errors.append(f"Provider must be a string, got {type(provider).__name__}")
            return
        
        provider = provider.strip().lower()
        
        if provider not in SUPPORTED_PROVIDERS:
            self.errors.append(
                f"Unsupported provider '{provider}'. "
                f"Supported providers: {', '.join(SUPPORTED_PROVIDERS)}"
            )
    
    def _validate_instance_id(self, instance_id: str) -> None:
        """Validate instance ID format"""
        if not isinstance(instance_id, str):
            self.errors.append(f"Instance ID must be a string, got {type(instance_id).__name__}")
            return
        
        instance_id = instance_id.strip()
        
        if not instance_id:
            return  # Empty is OK, will be auto-generated
        
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
        
        if timeout < 3:
            self.errors.append("Timeout must be >= 3 seconds")

        if timeout > 3600:
            self.errors.append("Timeout must be <= 3600 seconds (1 hour)")

    def _validate_stream_timeout(self, stream_timeout: Any) -> None:
        """Validate stream_timeout value"""
        if stream_timeout is None:
            return

        if not isinstance(stream_timeout, int):
            self.errors.append(f"Stream timeout must be an integer, got {type(stream_timeout).__name__}")
            return

        if stream_timeout < 3:
            self.errors.append("Stream timeout must be >= 3 seconds")

        if stream_timeout > 3600:
            self.errors.append("Stream timeout must be <= 3600 seconds (1 hour)")

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
            # Single capability as string is OK
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
        
        # Required fields
        normalized['name'] = data.get('name', '').strip()
        normalized['api_base'] = data.get('api_base', '').strip()
        
        # Optional with defaults
        normalized['provider'] = data.get('provider', 'openai_like').strip().lower()
        normalized['priority'] = data.get('priority', 1)
        normalized['timeout'] = data.get('timeout')  # None means inherit from routing timeout
        normalized['stream_timeout'] = data.get('stream_timeout')  # None means inherit from timeout
        normalized['max_retries'] = data.get('max_retries', 3)
        normalized['supports_streaming'] = data.get('supports_streaming', True)
        normalized['is_healthy'] = True
        
        # Optional fields
        if data.get('api_key'):
            normalized['api_key'] = data['api_key'].strip()
        
        if data.get('instance_id'):
            normalized['instance_id'] = data['instance_id'].strip()
        
        # Capabilities
        if isinstance(data.get('capabilities'), str):
            normalized['capabilities'] = ModelValidator.parse_capabilities(data['capabilities'])
        elif isinstance(data.get('capabilities'), list):
            normalized['capabilities'] = data['capabilities']
        else:
            normalized['capabilities'] = ['general']
        
        return normalized


