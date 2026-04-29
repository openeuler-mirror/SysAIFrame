"""
Copyright (C) 2025 CTyunOS. All Rights Reserved.
File: model_router.py
Desc: AI model routing module for SysAIFrame
     Focused on routing logic, model selection and request forwarding
Date: 2025-10-28
Author: Liu Mingran
"""

import time
import asyncio
import logging
import json
import contextvars
from functools import partial
from typing import Dict, List, Optional, Any, AsyncGenerator, Union

from sysai_framework.config import (
    ModelConfig,
    get_config_manager,
    ModelConfigManager,
    SPECIAL_MODEL_DEFAULT,
    SPECIAL_MODEL_MOCK,
    CAPABILITY_GENERAL
)
from sysai_framework.router.routing_strategy import RuntimeMode, LoadBalanceStrategy, BaseRoutingStrategy
from sysai_framework.router.strategies import (
    RoundRobinStrategy,
    WeightedStrategy,
    LeastBusyStrategy,
    LowestLatencyStrategy,
    UsageBasedStrategy
)
from sysai_framework.utils.provider_utils import get_llm_provider
from sysai_framework.llms.http_handler import get_http_handler
from sysai_framework.core.health_checker import HealthChecker
from sysai_framework.core.exceptions import (
    RetriableError, NonRetriableError, AllModelsFailed,
    AuthenticationError, InvalidRequestError, RateLimitError, TimeoutError
)

# Import metrics
try:
    from sysai_framework.core.metrics import (
        fallback_total,
        fallback_success,
        model_request_total,
        model_request_duration_seconds,
        retry_attempt_total,
        retry_exhausted_total,
        all_models_failed_total,
        streaming_chunks_total
    )
    METRICS_AVAILABLE = True
except ImportError:
    METRICS_AVAILABLE = False

logger = logging.getLogger(__name__)

# Timeout threshold constants for fallback mechanism
MIN_MEANINGFUL_TIMEOUT = 5.0  # Minimum time needed for a meaningful request attempt
MIN_USEFUL_TIMEOUT = 10.0     # Minimum time needed after backoff for a useful retry
MIN_FALLBACK_TIMEOUT = 10.0   # Minimum time needed for a fallback attempt (streaming)


class ModelRouter:
    """AI model router for SysAIFrame - focused on routing logic with health management"""
    pass


# Global router instance
_router_instance: Optional[ModelRouter] = None


def get_router() -> ModelRouter:
    """Get router instance (singleton pattern)"""
    global _router_instance
    if _router_instance is None:
        _router_instance = ModelRouter()
    return _router_instance


def reload_router() -> bool:
    """Reload router configuration"""
    global _router_instance
    if _router_instance:
        return _router_instance.reload_config()
    return False
