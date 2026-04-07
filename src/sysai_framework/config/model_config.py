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
