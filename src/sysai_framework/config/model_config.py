"""
Copyright (C) 2025 CTyunOS. All Rights Reserved.
File: model_config.py
Desc: Model configuration management for SysAIFrame
     Handles model configuration loading, validation and management
Date: 2025-10-28
Author: Liu Mingran
"""

import yaml
import logging
import os
import hashlib
import uuid
import fcntl
import time
import threading
from enum import Enum
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple, TYPE_CHECKING
from dataclasses import dataclass, field
from contextlib import contextmanager
from ruamel.yaml import YAML  # type: ignore
from ruamel.yaml.comments import CommentedMap, CommentedSeq  # type: ignore

if TYPE_CHECKING:
    from sysai_framework.core.status_codes import OperationResult

logger = logging.getLogger(__name__)


# Predefined capability constants (recommended for common use cases)
# Note: Users can define custom capabilities in YAML - these are just standard suggestions
CAPABILITY_GENERAL = "general"      # General chat capability
CAPABILITY_CODE = "code"           # Code-related capability
CAPABILITY_ANALYSIS = "analysis"   # Analysis task capability
CAPABILITY_CREATIVE = "creative"   # Creative writing capability

# Capability prefix for requests (e.g., "capability-code")
CAPABILITY_PREFIX = "capability-"

# Special model names
SPECIAL_MODEL_DEFAULT = "default"  # Use default model
SPECIAL_MODEL_MOCK = "mock"        # Use built-in Mock model


class UnhealthyReason(Enum):
    """Model unhealthy reason enumeration"""
    NONE = "none"                          # Healthy status
    LIGHTWEIGHT_CHECK_FAILED = "lightweight"  # Lightweight check failed
    ACTUAL_REQUEST_FAILED = "actual_request"  # Actual request failed


@dataclass
class ValidationMessage:
    """Validation message with level (error or warning)"""
    level: str  # "error" or "warning"
    message: str

    def __str__(self) -> str:
        return self.message


@dataclass
class HealthCheckConfig:
    """Health check configuration"""
    lightweight_enabled: bool = True
    lightweight_interval: int = 300  # seconds
    actual_request_enabled: bool = False  # Default disabled to avoid API costs
    actual_request_interval: int = 1200  # seconds
    timeout: int = 10  # seconds


@dataclass
class RetryPolicyConfig:
    """Retry policy configuration"""
    max_attempts: int = 3
    backoff_factor: int = 2
    base_delay: int = 1  # seconds
    max_delay: int = 30  # seconds


@dataclass
class LoadBalanceOptionsConfig:
    """Load balance strategy options configuration"""
    latency_buffer: float = 0.1  # lowest-latency: latency buffer ratio (0.0-1.0)
    latency_window: int = 10  # lowest-latency: latency sampling window size
    usage_window: int = 60  # usage-based: usage statistics window in seconds


@dataclass
class LoadBalanceConfig:
    """Load balance configuration"""
    strategy: str = "weighted"  # round-robin | weighted | least-busy | lowest-latency | usage-based
    options: LoadBalanceOptionsConfig = field(default_factory=LoadBalanceOptionsConfig)


@dataclass
class RuntimeConfig:
    """Runtime mode configuration"""
    mode: str = "default"  # default | load-balance
    load_balance: LoadBalanceConfig = field(default_factory=LoadBalanceConfig)


@dataclass
class RoutingConfig:
    """Routing configuration"""
    default_model: Optional[str] = None
    default_model_instance_id: Optional[str] = None
    health_check: HealthCheckConfig = field(default_factory=HealthCheckConfig)
    retry_policy: RetryPolicyConfig = field(default_factory=RetryPolicyConfig)
    timeout: int = 180  # Default timeout for LLM requests (3 minutes, suitable for complex text generation)
    runtime: RuntimeConfig = field(default_factory=RuntimeConfig)  # Runtime mode configuration


@dataclass
class ModelConfig:
    """
    Model configuration data structure for SysAIFrame
    """
    name: str
    instance_id: Optional[str] = None  # Unique instance identifier
    provider: Optional[str] = None  # Provider type (dashscope, moonshot, etc.)
    api_base: Optional[str] = None  # API base URL
    api_key: Optional[str] = None   # API key
    endpoint: Optional[str] = None  # Legacy field, use api_base instead
    priority: int = 1
    weight: int = 1  # Load balance weight (used in weighted strategy)
    capabilities: List[str] = None
    supports_streaming: bool = True
    timeout: int = 30
    max_retries: int = 3
    is_healthy: bool = True

    # Health status fields (managed by HealthChecker)
    connection_health: bool = True  # Lightweight check (HTTP HEAD) health status
    last_health_check: Optional[datetime] = None
    consecutive_failures: int = 0
    consecutive_successes: int = 0
    health_check_enabled: bool = True
    unhealthy_reason: UnhealthyReason = field(default=UnhealthyReason.NONE)

    # Fine-grained lock for thread safety
    _health_lock: threading.Lock = field(default_factory=threading.Lock, repr=False, compare=False)

    def __post_init__(self):
        if self.capabilities is None:
            self.capabilities = [CAPABILITY_GENERAL]  # Default to general capability
        # Support legacy 'endpoint' field by mapping it to 'api_base'
        if self.endpoint and not self.api_base:
            self.api_base = self.endpoint
        # Generate instance_id if not provided
        if not self.instance_id:
            self.instance_id = self._generate_instance_id()
        # Ensure unhealthy_reason is proper enum
        if not isinstance(self.unhealthy_reason, UnhealthyReason):
            self.unhealthy_reason = UnhealthyReason.NONE

    def _generate_instance_id(self) -> str:
        """
        Generate instance_id based on name + api_base + api_key (similar to litellm)
        This ensures the same configuration always generates the same instance_id
        """
        parts = [self.name]
        if self.api_base:
            parts.append(self.api_base)
        if self.api_key:
            parts.append(self.api_key)

        concat_str = "".join(parts)
        hash_object = hashlib.sha256(concat_str.encode())
        return hash_object.hexdigest()[:16]  # Use first 16 chars for readability


class ModelConfigManager:
    """Model configuration manager - handles loading, validation and management"""

    def __init__(self, config_path: str = "config/models.yaml", allow_create_default: bool = True):
        self.config_path = config_path
        self.allow_create_default = allow_create_default
        self.models: Dict[str, ModelConfig] = {}
        self._lock = threading.RLock()
        self._yaml = YAML()
        self._last_modified = 0.0
        self._loaded = False
        self._routing_config: RoutingConfig = RoutingConfig()

        if allow_create_default or os.path.exists(config_path):
            self.load_config()

    def load_config(self) -> None:
        """Load configuration from YAML file"""
        if not os.path.exists(self.config_path):
            if self.allow_create_default:
                self._create_default_config_file()
            else:
                logger.warning(f"Config file not found: {self.config_path}")
                return

        current_mtime = os.path.getmtime(self.config_path)
        if current_mtime == self._last_modified and self._loaded:
            return

        with self._lock:
            yaml_content = ""
            with open(self.config_path, 'r') as f:
                yaml_content = f.read()

            if not yaml_content.strip():
                yaml_content = self._get_default_config()

            config = self._yaml.loads(yaml_content)
            self.models, _, _ = self._process_models_config(config)
            self._routing_config = self._parse_routing_config(config.get('routing', {}))
            self._last_modified = current_mtime
            self._loaded = True

    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration dictionary"""
        return {
            "models": [],
            "routing": {}
        }

    def _process_models_config(self, config: Dict[str, Any]) -> Tuple[Dict[str, ModelConfig], Dict[str, List[str]], List[Dict[str, Any]]]:
        """Process models configuration"""
        models_config = config.get('models', [])
        models: Dict[str, ModelConfig] = {}
        name_to_instances: Dict[str, List[str]] = {}
        models_to_write_back: List[Dict[str, Any]] = []

        for model_dict in models_config:
            model_config = self._parse_model_config(model_dict)
            if model_config:
                models[model_config.instance_id] = model_config
                if model_config.name not in name_to_instances:
                    name_to_instances[model_config.name] = []
                name_to_instances[model_config.name].append(model_config.instance_id)
                models_to_write_back.append(model_dict)

        return models, name_to_instances, models_to_write_back

    def _parse_model_config(self, model_dict: Dict[str, Any]) -> Optional[ModelConfig]:
        """Parse single model configuration"""
        try:
            name = model_dict.get('name')
            if not name:
                logger.warning("Model config missing 'name' field")
                return None
            return ModelConfig(**model_dict)
        except Exception as e:
            logger.error(f"Failed to parse model config: {e}")
            return None

    def _parse_routing_config(self, routing_dict: Dict[str, Any]) -> RoutingConfig:
        """Parse routing configuration"""
        return RoutingConfig(
            default_model=routing_dict.get('default_model'),
            default_model_instance_id=routing_dict.get('default_model_instance_id'),
            timeout=routing_dict.get('timeout', 180)
        )

    def get_model(self, model_name_or_instance_id: str) -> Optional[ModelConfig]:
        """Get model by name or instance_id"""
        if model_name_or_instance_id in self.models:
            return self.models[model_name_or_instance_id]
        for model in self.models.values():
            if model.name == model_name_or_instance_id:
                return model
        return None

    def list_models(self, model_name: Optional[str] = None) -> List[ModelConfig]:
        """List all models or models with specific name"""
        if model_name:
            return [m for m in self.models.values() if m.name == model_name]
        return list(self.models.values())

    def get_default_model(self) -> Optional[ModelConfig]:
        """Get default model"""
        default_name = self._routing_config.default_model
        if default_name:
            return self.get_model(default_name)
        if self.models:
            return next(iter(self.models.values()))
        return None

    def add_model(self, model_config: ModelConfig) -> bool:
        """Add a model"""
        if model_config.instance_id in self.models:
            logger.warning(f"Model already exists: {model_config.instance_id}")
            return False
        self.models[model_config.instance_id] = model_config
        return True

    def delete_model(self, instance_id: str) -> bool:
        """Delete a model by instance_id"""
        if instance_id in self.models:
            del self.models[instance_id]
            return True
        return False

    def update_model(self, model_config: ModelConfig) -> bool:
        """Update an existing model"""
        if model_config.instance_id not in self.models:
            return False
        self.models[model_config.instance_id] = model_config
        return True

    @property
    def runtime_config(self) -> RuntimeConfig:
        """Get runtime configuration"""
        return self._routing_config.runtime