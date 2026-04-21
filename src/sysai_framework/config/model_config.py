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
