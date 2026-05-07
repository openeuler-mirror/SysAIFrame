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

    def __init__(self, config_manager=None, start_health_checker: bool = True):
        """
        Initialize the model router with config manager and health checker

        Args:
            config_manager: Model configuration manager instance
            start_health_checker: Whether to start health checker background thread
        """
        self.config_manager = config_manager or get_config_manager()

        # Initialize health checker
        self.health_checker = HealthChecker(self.config_manager)

        # Start background health checks if requested
        # Start health checker if any health check is enabled
        health_check = self.config_manager.routing_config.health_check
        if start_health_checker and (health_check.lightweight_enabled or health_check.actual_request_enabled):
            self.health_checker.start_background_checks()
            logger.debug("Health checker started")

        # Initialize routing strategy based on runtime mode
        self._init_routing_strategy()

        logger.debug("ModelRouter initialized with health management")

    def _init_routing_strategy(self) -> None:
        """Initialize routing strategy based on runtime mode configuration"""
        runtime_config = self.config_manager.runtime_config
        self.runtime_mode = RuntimeMode(runtime_config.mode) if runtime_config.mode else RuntimeMode.DEFAULT
        self.lb_strategy = None

        if self.runtime_mode == RuntimeMode.LOAD_BALANCE:
            strategy_type = runtime_config.load_balance.strategy
            try:
                strategy_enum = LoadBalanceStrategy(strategy_type)
                self.lb_strategy = self._create_strategy(strategy_enum)
                logger.info(f"Initialized load balance strategy: {strategy_type}")
            except ValueError:
                logger.warning(f"Unknown load balance strategy: {strategy_type}, falling back to default mode")
                self.runtime_mode = RuntimeMode.DEFAULT

    def _create_strategy(self, strategy: LoadBalanceStrategy) -> BaseRoutingStrategy:
        """Create routing strategy instance"""
        if strategy == LoadBalanceStrategy.ROUND_ROBIN:
            return RoundRobinStrategy(self.config_manager)
        elif strategy == LoadBalanceStrategy.WEIGHTED:
            return WeightedStrategy(self.config_manager)
        elif strategy == LoadBalanceStrategy.LEAST_BUSY:
            return LeastBusyStrategy(self.config_manager)
        elif strategy == LoadBalanceStrategy.LOWEST_LATENCY:
            return LowestLatencyStrategy(self.config_manager)
        elif strategy == LoadBalanceStrategy.USAGE_BASED:
            return UsageBasedStrategy(self.config_manager)
        else:
            # Fallback to weighted
            return WeightedStrategy(self.config_manager)


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
