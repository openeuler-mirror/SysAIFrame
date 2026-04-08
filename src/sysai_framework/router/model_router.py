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

                # Default mode: use priority-based selection
                healthy_models.sort(key=lambda m: (m.is_healthy, m.priority), reverse=True)
                selected = healthy_models[0]
                logger.debug(
                    f"Selected model '{selected.name}' (priority={selected.priority}) "
                    f"for capability '{capability}'"
                )
                return selected

        logger.warning(
            f"No healthy model found for capability '{capability}', fallback to default"
        )
        return self._select_default_model()

    def _get_mock_model(self) -> ModelConfig:
        """
        Return built-in mock model configuration

        Mock model uses existing mock response generators and doesn't need
        complex configuration since it doesn't make real API calls.
        """
        return ModelConfig(
            name=SPECIAL_MODEL_MOCK,
            provider="mock",
            is_healthy=True
        )

    def route_chat_completion(
                            model: str,
                            messages: List[Dict[str, Any]],
                            stream: bool = False,
                            model_config: Optional[ModelConfig] = None,
                            **kwargs) -> Union[Dict[str, Any], AsyncGenerator[str, None]]:
        """
        Synchronous chat completion routing

        This is the main entry point for chat completion routing.
        Handles both streaming and non-streaming in a single method.

        Args:
            model: Model name (used if model_config is None)
            messages: Chat messages
            stream: Whether to stream response
            model_config: Pre-selected model config (used if provided, skips model selection)
            **kwargs: Additional parameters

        Returns:
            Dict for non-streaming, AsyncGenerator for streaming
        """
        logger.debug(
            f"Routing chat completion for model: {model}, "
            f"stream: {stream}, model_config provided: {model_config is not None}"
        )

        # 1. Get model configuration
        # If model_config is provided (e.g., from fallback mechanism), use it directly
        # Otherwise, select model using select_model (for standalone calls)
        if model_config is not None:
            selected_config = model_config
            logger.debug(f"Using pre-selected model config: {selected_config.name} (instance_id: {selected_config.instance_id})")
        else:
            selected_config = self.select_model(model)
            if not selected_config:
                # Check if no models are configured at all
                if not self.config_manager.models or len(self.config_manager.models) == 0:
                    raise ValueError("No models configured")
                else:
                    # Models are configured but none are available/healthy
                    raise ValueError("No healthy models available")

        # Use selected_config for the rest of the method
        model_config = selected_config

        # 2. Special handling for mock model
        if model_config.name == SPECIAL_MODEL_MOCK or model_config.provider == "mock":
            logger.debug("Using mock model, returning mock response")
            if stream:
                return self._generate_mock_stream_response(model_config, messages, **kwargs)
            else:
                return self._generate_mock_response(model_config, messages, **kwargs)

        # 3. Identify provider
        actual_model, provider, api_key, api_base = get_llm_provider(
            model=model_config.name,
            custom_llm_provider=model_config.provider,
            api_base=model_config.api_base,
            api_key=model_config.api_key
        )

        logger.debug(f"Provider detected: {provider}, actual_model: {actual_model}")

        # 4. Get provider config
        provider_config = self._get_provider_config(provider)

        # 5. Call HTTP handler directly

        http_handler = get_http_handler()
        # Use routing_config.timeout as default, matching fallback logic
        # Default timeout is 180s (3 minutes) for LLM requests
        # LLM requests may take longer due to response generation and large response bodies
        routing_timeout = self.config_manager.routing_config.timeout if self.config_manager else 180
        timeout = kwargs.get('timeout', float(routing_timeout))

        try:
            return http_handler.completion(
                provider_config=provider_config,
                model=actual_model,
                messages=messages,
                api_base=api_base,
                api_key=api_key,
                optional_params=kwargs,
                stream=stream,
                timeout=timeout
            )
        except (RetriableError, NonRetriableError, AllModelsFailed) as e:
            # Re-raise known exception types directly
            # These are already properly typed exceptions from http_handler
            logger.error(
                f"Exception in route_chat_completion for {model_config.name}: {e}",
                exc_info=True
            )
            raise
        except Exception as e:
            # For unknown exceptions, log and re-raise
            # The upper layer (handle_exception_with_logging) will handle conversion
            logger.error(
                f"Unexpected exception in route_chat_completion for {model_config.name}: {e}",
                exc_info=True
            )
            raise

    def _get_provider_config(self, provider: str):
        """
        Get configuration class for specific provider

        Returns the appropriate BaseConfig subclass for the given provider.
        Each config handles provider-specific request/response transformations.
        """
        if provider == "dashscope":
            from sysai_framework.llms.dashscope.chat.transformation import DashScopeChatConfig
            return DashScopeChatConfig()
        elif provider == "moonshot":
            from sysai_framework.llms.moonshot.chat.transformation import MoonshotChatConfig
            return MoonshotChatConfig()
        elif provider == "deepseek":
            from sysai_framework.llms.deepseek.chat.transformation import DeepSeekChatConfig
            return DeepSeekChatConfig()
        else:  # openai_like or other Chat Completion API compatible providers
            from sysai_framework.llms.openai_like.chat.transformation import OpenAILikeChatConfig
            return OpenAILikeChatConfig()

    async def route_chat_acompletion(
                                   model: str,
                                   messages: List[Dict[str, Any]],
                                   stream: bool = False,
                                   **kwargs):
        """
        Asynchronous chat completion routing with fallback

        For streaming requests, this method implements fallback by wrapping
        the generator to catch exceptions during iteration and automatically
        try fallback models.

        For non-streaming requests, it delegates to route_chat_completion_with_fallback.

        Args:
            model: Model name
            messages: Chat messages
            stream: Whether to stream response
            **kwargs: Additional parameters

        Returns:
            Dict for non-streaming, AsyncGenerator for streaming

        Raises:
            AllModelsFailed: If all fallback models fail
        """
        # Prepare completion kwargs
        completion_kwargs = {
            'model': model,
            'messages': messages,
            'stream': stream,
        }

        try:
            if stream:
                # Streaming: use generator-based fallback approach
                # 1. Get initial model and generator
                model_config = self.select_model(model)
                if not model_config:
                    raise ValueError(f"No model available for: {model}")

                # 2. Call route_chat_completion to get initial generator
                # (not route_chat_completion_with_fallback, to avoid nested fallback)
                # Note: route_chat_completion is sync but returns AsyncGenerator for streaming
                initial_generator = self.route_chat_completion(
                    model=model_config.name,
                    messages=messages,
                    stream=True,
                    model_config=model_config,
                    **kwargs
                )

                # 3. Wrap with fallback logic
                # Note: _acompletion_streaming_with_fallback is an async generator function,
                # so we call it directly without await (it returns AsyncGenerator)
                return self._acompletion_streaming_with_fallback(
                    generator=initial_generator,
                    model=model,
                    messages=messages,
                    original_model_config=model_config,
                    requested_model=model,
                    **kwargs
                )
            else:
                # Non-streaming: use original fallback approach
                func = partial(
                    self.route_chat_completion_with_fallback,
                    **completion_kwargs,
                    **kwargs
                )

                # Add the context to the function
                ctx = contextvars.copy_context()
                func_with_context = partial(ctx.run, func)

                # Run sync function in thread pool executor
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(None, func_with_context)
                return response

        except AllModelsFailed as e:
            # All fallback models failed
            logger.error(f"All models failed after fallback: {e.attempted_models}")
            raise
        except Exception as e:
            logger.error(f"Error in async completion routing: {e}")
            raise

    def _generate_mock_response(self,
                              model_config: ModelConfig,
                              messages: List[Dict[str, Any]],
                              **kwargs) -> Dict[str, Any]:
        """Generate mock response for testing"""
        # Simulate processing time
        time.sleep(0.1)

        # Build response
        response = {
            "id": f"chatcmpl-mock-{int(time.time())}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": model_config.name,
            "choices": [{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": f"This is a mock response from {model_config.name}. Your message has been received."
                },
                "finish_reason": "stop"
            }],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 15,
                "total_tokens": 25
            }
        }

        logger.debug(f"Generated mock response for model: {model_config.name}")
        return response

    async def _generate_mock_stream_response(
                                           model_config: ModelConfig,
                                           messages: List[Dict[str, Any]],
                                           **kwargs) -> AsyncGenerator[str, None]:
        """Generate mock streaming response for testing"""
        response_id = f"chatcmpl-mock-{int(time.time())}"
        created_time = int(time.time())

        # Send initial chunk
        initial_chunk_data = {
            "id": response_id,
            "object": "chat.completion.chunk",
            "created": created_time,
            "model": model_config.name,
            "choices": [{
                "index": 0,
                "delta": {"role": "assistant", "content": ""},
                "finish_reason": None
            }]
        }
        yield f"data: {json.dumps(initial_chunk_data, ensure_ascii=False)}\n\n"

        # Simulate streaming content
        content_parts = [
            f"This is a mock streaming response from {model_config.name}.",
            "Your message has been received,",
            "processing in progress...",
            "Processing completed!"
        ]

        for i, part in enumerate(content_parts):
            await asyncio.sleep(0.2)  # Simulate processing delay
            chunk_data = {
                "id": response_id,
                "object": "chat.completion.chunk",
                "created": created_time,
                "model": model_config.name,
                "choices": [{
                    "index": 0,
                    "delta": {"content": part},
                    "finish_reason": None
                }]
            }
            # Convert to SSE format
            yield f"data: {json.dumps(chunk_data, ensure_ascii=False)}\n\n"

        # Send final chunk
        final_chunk_data = {
            "id": response_id,
            "object": "chat.completion.chunk",
            "created": created_time,
            "model": model_config.name,
            "choices": [{
                "index": 0,
                "delta": {},
                "finish_reason": "stop"
            }]
        }
        yield f"data: {json.dumps(final_chunk_data, ensure_ascii=False)}\n\n"

        # Send done signal
        yield "data: [DONE]\n\n"

        logger.debug(f"Generated mock stream response for model: {model_config.name}")

    def get_routing_status(self) -> Dict[str, Any]:
        """Get routing status information"""
        return self.config_manager.get_model_status()

    def get_health_statistics(self) -> Dict[str, Any]:
        """Get health statistics from health checker"""
        return self.health_checker.get_health_statistics()

    def trigger_health_check(self, model_name: Optional[str] = None):
        """
        Manually trigger health check

        Args:
            model_name: If provided, check only this model; otherwise check all
        """
        if model_name:
            model_config = self.config_manager.get_model_config(model_name)
            if model_config:
                self.health_checker.check_endpoint_lightweight(model_config)
                if self.config_manager.routing_config.health_check.actual_request_enabled:
                    self.health_checker.check_model_actual_request(model_config)
        else:
            # Check all models
            actual_request_enabled = self.config_manager.routing_config.health_check.actual_request_enabled
            for model_config in self.config_manager.models.values():
                if not model_config.health_check_enabled:
                    continue

                # Always trigger lightweight check
                self.health_checker.check_endpoint_lightweight(model_config)

                # Trigger actual request check if enabled and connection_health is True
                if actual_request_enabled and model_config.connection_health:
                    self.health_checker.check_model_actual_request(model_config)

    async def _acompletion_streaming_with_fallback(
        self,
        generator: AsyncGenerator[str, None],
        model: str,
        messages: List[Dict[str, Any]],
        original_model_config: ModelConfig,
        requested_model: Optional[str] = None,
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """
        Wrap streaming generator with automatic fallback on error

        This method implements fallback for streaming requests:
        - Catches exceptions during generator iteration
        - Automatically tries fallback models on failure
        - Records health status for each attempt
        - Enforces global timeout across all fallback attempts

        Args:
            generator: Initial async generator from route_chat_completion
            model: Original model name
            messages: Chat messages
            original_model_config: Initial model configuration
            requested_model: Original user request (for fallback list building)
            **kwargs: Additional parameters for route_chat_completion

        Yields:
            Chunks from the successful model's generator

        Raises:
            AllModelsFailed: If all models (including fallbacks) fail or global timeout exceeded
        """
        # Global timeout tracking
        fallback_start_time = time.time()
        routing_timeout = self.config_manager.routing_config.timeout if self.config_manager else 180
        total_timeout = kwargs.get('timeout', float(routing_timeout))

        # Max fallback depth control (inspired by LiteLLM)
        max_fallbacks = getattr(self.config_manager.routing_config, 'max_fallbacks', 5) if self.config_manager else 5

        current_generator = generator
        current_model_config = original_model_config
        attempted_models = [original_model_config.name]

        # Build fallback list once
        fallback_candidates = self._build_fallback_list(
            original_model_config.name,
            requested_model or model
        )

        fallback_idx = 0
        fallback_depth = 0
        first_chunk_read = False
        start_time = time.time()

    def _create_streaming_generator_for_fallback(
        self,
        model_config: ModelConfig,
        messages: List[Dict[str, Any]],
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """
        Create a new streaming generator for fallback model

        This is called when the current streaming model fails and we need
        to try a fallback model.

        Args:
            model_config: Fallback model configuration
            messages: Chat messages
            **kwargs: Additional parameters

        Returns:
            AsyncGenerator for the fallback model's streaming response

        Raises:
            Exception: If model invocation fails
        """
        # Call route_chat_completion directly (not with_fallback)
        # to avoid nested fallback logic
        # Note: route_chat_completion is sync and returns AsyncGenerator for streaming
        return self.route_chat_completion(
            model=model_config.name,
            messages=messages,
            stream=True,
            model_config=model_config,
            **kwargs
        )

    def _build_fallback_list(self, original_model_name: str,
                            requested_model: Optional[str] = None) -> List[ModelConfig]:
        """
        Build fallback list dynamically based on request type

        Strategy:
        1. Specific model -> same model other instances
        2. "default" -> all healthy models by priority
        3. "capability-xxx" -> same capability + general capability
        4. "mock" -> no fallback

        Args:
            original_model_name: Original model name that failed
            requested_model: Original user request string

        Returns:
            List of ModelConfig to try as fallbacks
        """
        fallback_list = []

        # Mock model: no fallback
        if original_model_name == SPECIAL_MODEL_MOCK:
            return []


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
