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

    def get_available_models(self) -> List[str]:
        """Get list of available models"""
        return self.config_manager.get_available_models()

    def get_model_config(self, model_name: str) -> Optional[ModelConfig]:
        """Get model configuration by name"""
        return self.config_manager.get_model_config(model_name)

    def _should_consider_health(self) -> bool:
        """
        Check if health status should be considered when selecting models

        Returns:
            True if health check is enabled (lightweight or actual_request), False otherwise
        """
        health_check = self.config_manager.routing_config.health_check
        return health_check.lightweight_enabled or health_check.actual_request_enabled

    def select_model(self, requested_model: Optional[str] = None) -> Optional[ModelConfig]:
        """
        Select model for routing - enhanced with capability-based selection and instance support

        Supported formats:
        1. None or empty string -> Use default model
        2. "default" -> Use default model
        3. "mock" -> Return built-in Mock model
        4. "capability-xxx" -> Select by capability (e.g., capability-code)
        5. "model_name" -> Select best instance of that model (load balancing)
        6. "model_name:instance_id" -> Select specific instance

        Args:
            requested_model: Model identifier (can be name, "default", "mock", "capability-xxx",
                            or "model_name:instance_id")

        Returns:
            ModelConfig or None if no suitable model found
        """
        # Case 1: None, empty, or "default" -> use default model
        if not requested_model or requested_model == SPECIAL_MODEL_DEFAULT:
            logger.debug("Using default model selection")
            return self._select_default_model()

        # Case 2: "mock" -> return built-in mock model
        if requested_model == SPECIAL_MODEL_MOCK:
            logger.debug("Using built-in mock model")
            return self._get_mock_model()

        # Case 3: Capability request (e.g., "capability-code")
        if ModelConfigManager.is_capability_request(requested_model):
            capability = ModelConfigManager.extract_capability(requested_model)
            logger.debug(f"Selecting model by capability: {capability}")
            return self._select_by_capability(capability)

        # Case 4: Specific model name or model_name:instance_id
        # Check if it's model_name:instance_id format
        if ':' in requested_model:
            # Specific instance requested, bypass load balancing
            model_config = self.config_manager.get_model_config(requested_model)
            if model_config and (not self._should_consider_health() or model_config.is_healthy):
                logger.debug(
                    f"Selected requested model: {requested_model} "
                    f"(instance_id={model_config.instance_id})"
                )
                return model_config
        else:
            # Model name only - use load balancing if enabled
            models = self.config_manager.get_models_by_name(requested_model)
            if models:
                should_consider_health = self._should_consider_health()
                healthy_models = [
                    m for m in models
                    if not should_consider_health or m.is_healthy
                ]

                if healthy_models:
                    # Use load balance strategy if enabled
                    if self.runtime_mode == RuntimeMode.LOAD_BALANCE and self.lb_strategy:
                        selected = self.lb_strategy.select_deployment(healthy_models)
                        if selected:
                            logger.debug(
                                f"Load balance selected model: {requested_model} "
                                f"(instance_id={selected.instance_id})"
                            )
                            return selected

                    # Default mode: use priority-based selection
                    healthy_models.sort(key=lambda m: (m.is_healthy, m.priority), reverse=True)
                    selected = healthy_models[0]
                    logger.debug(
                        f"Selected requested model: {requested_model} "
                        f"(instance_id={selected.instance_id})"
                    )
                    return selected

        # Check if any models are configured at all
        if not self.config_manager.models:
            logger.error("No models configured")
            return None

        logger.debug(
            f"Requested model '{requested_model}' not available or unhealthy, "
            f"fallback to default"
        )
        return self._select_default_model()

    def _select_default_model(self) -> Optional[ModelConfig]:
        """
        Select the default model

        If default_model_instance_id is specified, use that specific instance.
        Otherwise, select the best instance of the default model name.
        In load-balance mode, uses routing strategy to select from candidates.
        """
        # First check if any models are configured
        if not self.config_manager.models or len(self.config_manager.models) == 0:
            logger.error("No models configured")
            return None

        default_model = self.config_manager.default_model
        default_instance_id = self.config_manager.default_model_instance_id

        if default_instance_id:
            # Use specific instance (bypass load balancing)
            model_config = self.config_manager.get_model_by_instance_id(default_instance_id)
            if model_config and (not self._should_consider_health() or model_config.is_healthy):
                logger.debug(
                    f"Selected default model instance: {default_model} "
                    f"(instance_id={default_instance_id})"
                )
                return model_config
        elif default_model:
            # Get all instances of default model
            candidates = self.config_manager.get_models_by_name(default_model)
            if candidates:
                # Filter by health if needed
                should_consider_health = self._should_consider_health()
                healthy_candidates = [
                    m for m in candidates
                    if not should_consider_health or m.is_healthy
                ]

                if healthy_candidates:
                    # Use load balance strategy if enabled
                    if self.runtime_mode == RuntimeMode.LOAD_BALANCE and self.lb_strategy:
                        selected = self.lb_strategy.select_deployment(healthy_candidates)
                        if selected:
                            logger.debug(
                                f"Load balance selected default model: {default_model} "
                                f"(instance_id={selected.instance_id})"
                            )
                            return selected

                    # Default mode: use priority-based selection
                    healthy_candidates.sort(key=lambda m: (m.is_healthy, m.priority), reverse=True)
                    selected = healthy_candidates[0]
                    logger.debug(
                        f"Selected best instance of default model: {default_model} "
                        f"(instance_id={selected.instance_id})"
                    )
                    return selected

        # Fallback: any available healthy model
        logger.warning("Default model not available, selecting any available model")
        return self._select_any_available_model()

    def _select_any_available_model(self) -> Optional[ModelConfig]:
        """Select any available healthy model instance"""
        should_consider_health = self._should_consider_health()

        if should_consider_health:
            all_healthy = self.config_manager.get_all_healthy_models()
        else:
            all_healthy = list(self.config_manager.models.values())

        if not all_healthy:
            logger.error("No healthy models available")
            return None

        # Use load balance strategy if enabled
        if self.runtime_mode == RuntimeMode.LOAD_BALANCE and self.lb_strategy:
            selected = self.lb_strategy.select_deployment(all_healthy)
            if selected:
                logger.debug(f"Load balance selected model: {selected.name}")
                return selected

        # Default: use priority-based selection
        all_healthy.sort(key=lambda m: (m.is_healthy, m.priority), reverse=True)
        selected = all_healthy[0]
        logger.debug(f"Selected model by priority: {selected.name}")
        return selected

    def _select_by_capability(self, capability: str) -> Optional[ModelConfig]:
        """
        Select model by capability (only healthy models)

        Args:
            capability: The capability name (e.g., "code", "general")

        Returns:
            ModelConfig with highest priority for the capability, or default model
        """
        # get_models_by_capability already filters by is_healthy if health check is enabled
        models = self.config_manager.get_models_by_capability(capability)
        if models:
            # Further filter by health status if health check is enabled
            should_consider_health = self._should_consider_health()
            if should_consider_health:
                healthy_models = [m for m in models if m.is_healthy]
            else:
                healthy_models = models

            if healthy_models:
                # Use load balance strategy if enabled
                if self.runtime_mode == RuntimeMode.LOAD_BALANCE and self.lb_strategy:
                    selected = self.lb_strategy.select_deployment(healthy_models)
                    if selected:
                        logger.debug(
                            f"Load balance selected model '{selected.name}' "
                            f"(instance_id={selected.instance_id}) for capability '{capability}'"
                        )
                        return selected


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
