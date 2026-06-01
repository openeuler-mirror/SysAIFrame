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
    DEFAULT_ROUTING_TIMEOUT,
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

    def _resolve_model_timeout(
        self,
        model_config: ModelConfig,
        routing_timeout: float,
        explicit_timeout: Optional[float] = None,
    ) -> float:
        """Resolve effective timeout for a single model attempt.

        Returns the minimum of all applicable limits:
        - model_config.timeout: per-model override (strictest model-level limit)
        - explicit_timeout: remaining time budget from fallback
        - routing_timeout: global ceiling

        Model timeout always takes effect when configured, while explicit_timeout
        further constrains it in fallback scenarios where time is running out.
        """
        candidates = []
        if model_config.timeout is not None:
            candidates.append(float(model_config.timeout))
        if explicit_timeout is not None:
            candidates.append(explicit_timeout)
        candidates.append(routing_timeout)
        return min(candidates)

    def _resolve_model_stream_timeout(
        self,
        model_config: ModelConfig,
        routing_timeout: float,
        explicit_timeout: Optional[float] = None,
    ) -> float:
        """Resolve effective stream timeout for streaming requests.

        Returns the minimum of all applicable limits:
        - model_config.stream_timeout (explicit stream override)
        - model_config.timeout (fallback when stream_timeout is None, backward compat)
        - explicit_timeout (remaining time budget from fallback)
        - routing_timeout (global ceiling)

        Inheritance chain: stream_timeout -> timeout -> routing_timeout
        """
        candidates = []
        if model_config.stream_timeout is not None:
            candidates.append(float(model_config.stream_timeout))
        elif model_config.timeout is not None:
            candidates.append(float(model_config.timeout))
        if explicit_timeout is not None:
            candidates.append(explicit_timeout)
        candidates.append(routing_timeout)
        return min(candidates)

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
        7. "instance_id" -> Select specific instance by bare instance_id

        Args:
            requested_model: Model identifier (can be name, instance_id, "default", "mock",
                            "capability-xxx", or "model_name:instance_id")

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
            if model_config:
                if not self._should_consider_health() or model_config.is_healthy:
                    logger.debug(
                        f"Selected requested model: {requested_model} "
                        f"(instance_id={model_config.instance_id})"
                    )
                    return model_config
                # Instance exists but is unhealthy - still attempt request
                logger.warning(
                    f"Requested instance '{requested_model}' is unhealthy, "
                    f"will attempt request anyway before falling back"
                )
                return model_config
        else:
            # Try instance_id lookup first (bare instance_id without model_name prefix)
            model_config = self.config_manager.get_model_config(requested_model)
            if model_config:
                if not self._should_consider_health() or model_config.is_healthy:
                    logger.debug(
                        f"Selected model by instance_id: {requested_model}"
                    )
                    return model_config
                logger.warning(
                    f"Requested instance '{requested_model}' is unhealthy, "
                    f"will attempt request anyway"
                )
                return model_config

            # Model name lookup - use load balancing if enabled
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

                # Model exists but all instances are unhealthy
                # Still attempt the request - user explicitly chose this model
                models.sort(key=lambda m: m.priority, reverse=True)
                logger.warning(
                    f"Requested model '{requested_model}' is unhealthy, "
                    f"will attempt request anyway before falling back to other models"
                )
                return models[0]

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

        # Collect all healthy models
        candidates = []
        for model_config in self.config_manager.models.values():
            if not should_consider_health or model_config.is_healthy:
                candidates.append(model_config)

        if not candidates:
            if should_consider_health:
                logger.error("No healthy models available")
            else:
                logger.error("No models available")
            return None

        # Use load balance strategy if enabled
        if self.runtime_mode == RuntimeMode.LOAD_BALANCE and self.lb_strategy:
            selected = self.lb_strategy.select_deployment(candidates)
            if selected:
                logger.debug(
                    f"Load balance selected fallback model: {selected.name} "
                    f"(instance_id={selected.instance_id})"
                )
                return selected

        # Default mode: use priority-based selection
        candidates.sort(key=lambda m: (m.is_healthy, m.priority), reverse=True)
        selected = candidates[0]
        logger.debug(
            f"Selected fallback model: {selected.name} "
            f"(instance_id={selected.instance_id})"
        )
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

    def route_chat_completion(self,
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
        # Resolve timeout: use stream_timeout for streaming, timeout for non-streaming
        routing_timeout = self.config_manager.routing_config.timeout if self.config_manager else DEFAULT_ROUTING_TIMEOUT
        if stream:
            timeout = self._resolve_model_stream_timeout(model_config, float(routing_timeout), kwargs.get('timeout'))
        else:
            timeout = self._resolve_model_timeout(model_config, float(routing_timeout), kwargs.get('timeout'))

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
        elif provider == "volcengine":
            from sysai_framework.llms.volcengine.chat.transformation import VolcEngineChatConfig
            return VolcEngineChatConfig()
        elif provider == "zai":
            from sysai_framework.llms.zai.chat.transformation import ZAIChatConfig
            return ZAIChatConfig()
        elif provider == "minimax":
            from sysai_framework.llms.minimax.chat.transformation import MinimaxChatConfig
            return MinimaxChatConfig()
        else:  # openai_like or other Chat Completion API compatible providers
            from sysai_framework.llms.openai_like.chat.transformation import OpenAILikeChatConfig
            return OpenAILikeChatConfig()

    async def route_chat_acompletion(self,
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

    async def _generate_mock_stream_response(self,
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
        Manually trigger health check (with short-interval retry on failure)

        Args:
            model_name: If provided, check only this model; otherwise check all
        """
        if model_name:
            model_config = self.config_manager.get_model_config(model_name)
            if model_config:
                self.health_checker.trigger_check_model(model_config)
        else:
            # Check all models
            for model_config in self.config_manager.models.values():
                if not model_config.health_check_enabled:
                    continue
                self.health_checker.trigger_check_model(model_config)

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
        routing_timeout = self.config_manager.routing_config.timeout if self.config_manager else DEFAULT_ROUTING_TIMEOUT
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

        while True:
            # Check global timeout before each attempt
            elapsed_time = time.time() - fallback_start_time
            if elapsed_time >= total_timeout:
                logger.warning(
                    f"Global timeout ({total_timeout}s) exceeded after {elapsed_time:.1f}s for streaming request. "
                    f"Attempted models: {attempted_models}"
                )
                raise AllModelsFailed(
                    attempted_models=attempted_models,
                    last_exception=TimeoutError(f"Global timeout {total_timeout}s exceeded after {elapsed_time:.1f}s")
                )

            # Check fallback depth limit
            if fallback_depth >= max_fallbacks:
                logger.warning(
                    f"Max fallback depth ({max_fallbacks}) reached for streaming request. "
                    f"Attempted models: {attempted_models}"
                )
                raise AllModelsFailed(
                    attempted_models=attempted_models,
                    last_exception=Exception(f"Max fallback depth {max_fallbacks} exceeded")
                )
            try:
                # Try to iterate through current generator
                async for chunk in current_generator:
                    if not first_chunk_read:
                        # Successfully read first chunk, record success
                        first_chunk_read = True
                        duration = time.time() - start_time

                        if METRICS_AVAILABLE:
                            model_request_total.labels(
                                model=current_model_config.name,
                                status="success"
                            ).inc()
                            model_request_duration_seconds.labels(
                                model=current_model_config.name
                            ).observe(duration)

                            # Record fallback success if not first model
                            if fallback_idx > 0:
                                previous_model = attempted_models[-2]
                                fallback_success.labels(
                                    from_model=previous_model,
                                    to_model=current_model_config.name
                                ).inc()

                        self.health_checker.record_success(
                            current_model_config,
                            check_type="actual_request"
                        )
                        logger.debug(
                            f"Model {current_model_config.name} succeeded "
                            f"(streaming, first chunk received)"
                        )

                    # Record streaming chunk metric
                    if METRICS_AVAILABLE:
                        streaming_chunks_total.labels(
                            model=current_model_config.name
                        ).inc()

                    yield chunk

                # Generator exhausted successfully, we're done
                break

            except (RetriableError, NonRetriableError, Exception) as e:
                # Record failure for current model
                duration = time.time() - start_time

                if METRICS_AVAILABLE:
                    model_request_total.labels(
                        model=current_model_config.name,
                        status="retriable_error" if isinstance(e, RetriableError)
                               else "non_retriable_error"
                    ).inc()
                    model_request_duration_seconds.labels(
                        model=current_model_config.name
                    ).observe(duration)

                if self.health_checker._should_mark_unhealthy_on_user_request_failure(
                    current_model_config
                ):
                    self.health_checker.record_failure(
                        current_model_config,
                        str(e),
                        check_type="actual_request"
                    )

                logger.warning(
                    f"Streaming failed for {current_model_config.name}: {e}"
                )

                # Try fallback
                if fallback_idx >= len(fallback_candidates):
                    # No more fallback candidates
                    if METRICS_AVAILABLE:
                        all_models_failed_total.labels(
                            original_model=model
                        ).inc()

                    logger.error(
                        f"All models failed for streaming request. "
                        f"Attempted: {attempted_models}"
                    )
                    raise AllModelsFailed(
                        attempted_models=attempted_models,
                        last_exception=e
                    )

                # Check remaining time before trying fallback
                elapsed_time = time.time() - fallback_start_time
                remaining_time = total_timeout - elapsed_time

                if remaining_time < MIN_FALLBACK_TIMEOUT:
                    logger.warning(
                        f"Insufficient time remaining ({remaining_time:.1f}s) for fallback. "
                        f"Minimum {MIN_FALLBACK_TIMEOUT}s required. Attempted models: {attempted_models}"
                    )
                    raise AllModelsFailed(
                        attempted_models=attempted_models,
                        last_exception=TimeoutError(f"Insufficient time ({remaining_time:.1f}s) for fallback")
                    )

                # Get next fallback model
                next_model_config = fallback_candidates[fallback_idx]
                fallback_idx += 1
                fallback_depth += 1
                attempted_models.append(next_model_config.name)

                if METRICS_AVAILABLE:
                    fallback_total.labels(
                        from_model=current_model_config.name,
                        to_model=next_model_config.name
                    ).inc()

                logger.warning(
                    f"Fallback to {next_model_config.name} "
                    f"(attempt {fallback_idx + 1}/{len(fallback_candidates) + 1}, "
                    f"depth {fallback_depth}/{max_fallbacks}, "
                    f"remaining time {remaining_time:.1f}s)"
                )

                # Create new generator for fallback model with remaining timeout
                try:
                    # Resolve timeout for fallback model: min(model_stream_timeout, remaining_time)
                    fallback_kwargs = kwargs.copy()
                    fallback_timeout = self._resolve_model_stream_timeout(
                        model_config=next_model_config,
                        routing_timeout=total_timeout,
                        explicit_timeout=remaining_time
                    )
                    fallback_kwargs['timeout'] = fallback_timeout

                    logger.debug(
                        f"Creating fallback generator for {next_model_config.name} "
                        f"with timeout={fallback_timeout:.1f}s "
                        f"(remaining={remaining_time:.1f}s, model_config={next_model_config.timeout})"
                    )

                    # _create_streaming_generator_for_fallback returns AsyncGenerator directly
                    current_generator = self._create_streaming_generator_for_fallback(
                        model_config=next_model_config,
                        messages=messages,
                        **fallback_kwargs
                    )
                    current_model_config = next_model_config
                    first_chunk_read = False
                    start_time = time.time()
                    # Continue to next iteration to try this generator

                except Exception as fallback_error:
                    # Failed to create fallback generator
                    logger.error(
                        f"Failed to create fallback generator for "
                        f"{next_model_config.name}: {fallback_error}"
                    )
                    # Continue to next fallback candidate
                    continue

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

        # Capability request: fallback to same capability + general
        if requested_model and ModelConfigManager.is_capability_request(requested_model):
            capability = ModelConfigManager.extract_capability(requested_model)
            # Same capability models
            capability_models = self.config_manager.get_models_by_capability(capability)
            fallback_list.extend([m for m in capability_models if m.name != original_model_name])

            # General capability models (if different from requested capability)
            if capability != CAPABILITY_GENERAL:
                general_models = self.config_manager.get_models_by_capability(CAPABILITY_GENERAL)
                fallback_list.extend([m for m in general_models if m not in fallback_list])

            logger.debug(
                f"Built capability fallback list ({len(fallback_list)} candidates): "
                f"{[f'{m.name}({m.instance_id[:8]})' for m in fallback_list]}"
            )
            return fallback_list

        # Default or specific model request
        should_consider_health = self._should_consider_health()
        # 1. First try other instances of same model
        same_model_instances = self.config_manager.get_all_instances(original_model_name)
        if should_consider_health:
            healthy_same_model = [m for m in same_model_instances if m.is_healthy]
            # Include unhealthy same-name instances as low-priority fallback
            # since the user explicitly requested this model
            unhealthy_same_model = [m for m in same_model_instances if not m.is_healthy]
        else:
            healthy_same_model = same_model_instances
            unhealthy_same_model = []
        fallback_list.extend(healthy_same_model)
        # Append unhealthy same-name instances after healthy ones
        for m in unhealthy_same_model:
            if m not in fallback_list:
                fallback_list.append(m)
        logger.debug(
            f"Same model instances for '{original_model_name}': "
            f"{len(healthy_same_model)} healthy, {len(unhealthy_same_model)} unhealthy "
            f"out of {len(same_model_instances)} total"
        )

        # 2. Then try all other healthy models by priority
        if should_consider_health:
            all_healthy = self.config_manager.get_all_healthy_models()
        else:
            all_healthy = list(self.config_manager.models.values())
        logger.debug(
            f"All available models: {len(all_healthy)} total - "
            f"{[f'{m.name}({m.instance_id[:8]})' for m in all_healthy]}"
        )

        # Sort by priority (higher first)
        all_healthy.sort(key=lambda m: m.priority, reverse=True)

        # Filter: exclude original model name and already added instances
        other_healthy = [
            m for m in all_healthy
            if m.name != original_model_name and m not in fallback_list
        ]
        logger.debug(
            f"Other healthy models (excluding '{original_model_name}'): "
            f"{len(other_healthy)} candidates - "
            f"{[f'{m.name}({m.instance_id[:8]})' for m in other_healthy]}"
        )
        fallback_list.extend(other_healthy)

        logger.debug(
            f"Built fallback list with {len(fallback_list)} candidates: "
            f"{[f'{m.name}({m.instance_id[:8]})' for m in fallback_list]}"
        )
        return fallback_list

    def _calculate_backoff(
        self,
        attempt: int,
        model_config: Optional[ModelConfig] = None,
        fallback_list: Optional[List[ModelConfig]] = None,
        current_model_idx: Optional[int] = None,
        error: Optional[Exception] = None
    ) -> float:
        """
        Calculate smart backoff delay (inspired by LiteLLM)

        Features:
        - Returns 0 (immediate retry) if healthy alternatives exist
        - Considers Retry-After header (future enhancement)
        - Falls back to exponential backoff

        Args:
            attempt: Current attempt number (0-indexed)
            model_config: Current model configuration
            fallback_list: List of all fallback models
            current_model_idx: Index of current model in fallback list
            error: Exception that triggered the retry (may contain Retry-After info)

        Returns:
            Delay in seconds (0 for immediate retry)
        """
        retry_config = self.config_manager.routing_config.retry_policy

        # Smart backoff: check if healthy alternatives exist (same model name, different instance)
        if model_config and fallback_list and current_model_idx is not None:
            has_healthy_alternatives = any(
                m.name == model_config.name and
                m.instance_id != model_config.instance_id and
                m.is_healthy
                for m in fallback_list[current_model_idx+1:]
            )

            if has_healthy_alternatives:
                logger.debug(
                    f"Healthy alternatives available for {model_config.name}, "
                    f"immediate retry (0s delay)"
                )
                return 0.0

        # TODO: Check Retry-After header for rate limit errors
        # if error and isinstance(error, RateLimitError):
        #     if hasattr(error, 'retry_after'):
        #         return float(error.retry_after)

        # Normal exponential backoff
        delay = retry_config.base_delay * (retry_config.backoff_factor ** attempt)
        return min(delay, retry_config.max_delay)

    def should_retry_error(
        self,
        error: Exception,
        model_config: ModelConfig,
        fallback_list: List[ModelConfig],
        current_model_idx: int
    ) -> bool:
        """
        Smart decision on whether to retry current error (inspired by LiteLLM)

        Decision logic:
        1. Authentication/Non-retriable errors -> No retry
        2. Last model in fallback list -> Should retry (no alternatives)
        3. RateLimitError/TimeoutError with fallback available -> Skip retry, try fallback
        4. No healthy same-name instances -> Skip retry
        5. Otherwise -> Can retry

        Args:
            error: Exception that occurred
            model_config: Current model configuration
            fallback_list: List of all fallback models
            current_model_idx: Index of current model in fallback list

        Returns:
            True if should retry, False if should skip retry and try fallback
        """
        # 1. Non-retriable errors: don't retry
        if isinstance(error, (AuthenticationError, InvalidRequestError, NonRetriableError)):
            logger.info(
                f"Non-retriable error for {model_config.name}: {type(error).__name__}. "
                f"Skipping retry."
            )
            return False

        # 2. Last model: should retry (no fallback available)
        is_last_model = (current_model_idx >= len(fallback_list) - 1)
        if is_last_model:
            logger.debug(
                f"Last model in fallback list, will retry {model_config.name}"
            )
            return True

        # 3. RateLimitError/TimeoutError with fallback: skip retry, try fallback immediately
        if isinstance(error, (RateLimitError, TimeoutError)):
            logger.info(
                f"{type(error).__name__} for {model_config.name}. "
                f"Skipping retry, will try next fallback model."
            )
            return False

        # 4. Check for healthy same-name instances
        has_healthy_same_name = any(
            m.name == model_config.name and
            m.instance_id != model_config.instance_id and
            m.is_healthy
            for m in fallback_list[current_model_idx+1:]
        )

        if not has_healthy_same_name:
            logger.info(
                f"No healthy alternatives for {model_config.name}. "
                f"Skipping retry, will try different model."
            )
            return False

        # 5. Default: can retry
        return True

    def route_chat_completion_with_fallback(self,
                                           model: str,
                                           messages: List[Dict[str, Any]],
                                           stream: bool = False,
                                           **kwargs) -> Union[Dict[str, Any], AsyncGenerator[str, None]]:
        """
        Route chat completion with intelligent fallback and retry

        This method wraps route_chat_completion with:
        - Automatic retry for retriable errors
        - Intelligent model fallback on failure
        - Health status synchronous updates

        Args:
            model: Model name
            messages: Chat messages
            stream: Whether to stream
            **kwargs: Additional parameters

        Returns:
            Response or raises AllModelsFailed
        """
        retry_config = self.config_manager.routing_config.retry_policy
        attempted_models = []
        original_request = model

        # Get total timeout from kwargs, or use routing_config.timeout as default
        # Default timeout is 180s (3 minutes) for LLM requests
        # LLM requests may take longer due to response generation and large response bodies
        routing_timeout = self.config_manager.routing_config.timeout if self.config_manager else DEFAULT_ROUTING_TIMEOUT
        total_timeout = kwargs.get('timeout', float(routing_timeout))
        fallback_start_time = time.time()

        # Build initial fallback list
        model_config = self.select_model(model)
        if not model_config:
            raise ValueError("No models available")

        current_model = model_config.name
        fallback_candidates = self._build_fallback_list(current_model, original_request)

        # Remove duplicates based on instance_id
        # Use a set to track seen instance_ids to ensure each model instance is only tried once
        seen_instance_ids = {model_config.instance_id}
        fallback_list = [model_config]

        for candidate in fallback_candidates:
            if candidate.instance_id not in seen_instance_ids:
                seen_instance_ids.add(candidate.instance_id)
                fallback_list.append(candidate)

        logger.debug(
            f"Fallback list built: {len(fallback_list)} unique models: "
            f"{[f'{m.name}({m.instance_id[:8]})' for m in fallback_list]}"
        )

        # Try each model in fallback list
        for model_idx, model_to_try in enumerate(fallback_list):
            # Check if total timeout exceeded
            elapsed_time = time.time() - fallback_start_time
            remaining_time = total_timeout - elapsed_time

            if remaining_time <= 0:
                logger.warning(
                    f"Total timeout ({total_timeout}s) exceeded after {elapsed_time:.2f}s, "
                    f"stopping fallback. Attempted models: {', '.join(attempted_models)}"
                )
                break

            attempted_models.append(model_to_try.name)

            # Record fallback metric if not first model
            if model_idx > 0 and METRICS_AVAILABLE:
                previous_model = fallback_list[model_idx - 1].name
                fallback_total.labels(
                    from_model=previous_model,
                    to_model=model_to_try.name,
                    reason="health"
                ).inc()

            # Timeout allocation: resolve per-model timeout with remaining time budget
            # Uses min(model_timeout_override, remaining_time) to respect both limits
            model_timeout = self._resolve_model_timeout(
                model_config=model_to_try,
                routing_timeout=total_timeout,
                explicit_timeout=remaining_time
            )

            logger.debug(
                f"Timeout assignment for {model_to_try.name}: "
                f"allocated_timeout={model_timeout:.1f}s, "
                f"remaining_time={remaining_time:.1f}s, "
                f"model_config_timeout={model_to_try.timeout}"
            )

            # Retry logic for current model
            for attempt in range(retry_config.max_attempts):
                # Check if timeout exceeded before this attempt
                elapsed_time = time.time() - fallback_start_time
                if elapsed_time >= total_timeout:
                    logger.warning(
                        f"Total timeout ({total_timeout}s) exceeded, stopping retry for "
                        f"model {model_to_try.name} (attempt {attempt+1})"
                    )
                    break

                # Record retry metric
                if attempt > 0 and METRICS_AVAILABLE:
                    retry_attempt_total.labels(
                        model=model_to_try.name,
                        attempt_number=str(attempt + 1)
                    ).inc()

                start_time = time.time()

                try:
                    logger.info(
                        f"Attempting model {model_to_try.name} "
                        f"(attempt {attempt+1}/{retry_config.max_attempts}, "
                        f"fallback index {model_idx}/{len(fallback_list)})"
                    )

                    # Use the model timeout assigned at model level, but ensure it doesn't exceed actual remaining time
                    attempt_elapsed = time.time() - fallback_start_time
                    attempt_remaining = total_timeout - attempt_elapsed

                    # Check if we have sufficient time remaining
                    if attempt_remaining < MIN_MEANINGFUL_TIMEOUT:
                        logger.warning(
                            f"Insufficient time remaining ({attempt_remaining:.2f}s), "
                            f"minimum {MIN_MEANINGFUL_TIMEOUT}s required. "
                            f"Skipping retry for {model_to_try.name}"
                        )
                        break

                    # Use model timeout, but don't exceed actual remaining time
                    actual_timeout = min(model_timeout, attempt_remaining)

                    call_kwargs = kwargs.copy()
                    call_kwargs['timeout'] = actual_timeout
                    # Pass model_config to avoid redundant select_model call
                    # The fallback mechanism has already selected the appropriate model
                    response = self.route_chat_completion(
                        model=model_to_try.name,
                        messages=messages,
                        stream=stream,
                        model_config=model_to_try,  # Pass pre-selected model config
                        **call_kwargs
                    )

                    # Record success and return response
                    # Note: For streaming requests called from route_chat_acompletion,
                    # health status is managed by _acompletion_streaming_with_fallback.
                    # This method (route_chat_completion_with_fallback) is primarily used
                    # for non-streaming requests now.
                    if not (stream and isinstance(response, AsyncGenerator)):
                        # Non-streaming: record success immediately
                        duration = time.time() - start_time
                        if METRICS_AVAILABLE:
                            model_request_total.labels(
                                model=model_to_try.name,
                                status="success"
                            ).inc()
                            model_request_duration_seconds.labels(
                                model=model_to_try.name
                            ).observe(duration)

                            # Record fallback success if not first model
                            if model_idx > 0:
                                previous_model = fallback_list[model_idx - 1].name
                                fallback_success.labels(
                                    from_model=previous_model,
                                    to_model=model_to_try.name
                                ).inc()

                        self.health_checker.record_success(model_to_try, check_type="actual_request")
                        logger.debug(f"Model {model_to_try.name} succeeded")

                    return response

                except RetriableError as e:
                    # Retriable error: check if we should retry
                    duration = time.time() - start_time
                    if METRICS_AVAILABLE:
                        model_request_total.labels(
                            model=model_to_try.name,
                            status="retriable_error"
                        ).inc()
                        model_request_duration_seconds.labels(
                            model=model_to_try.name
                        ).observe(duration)

                    logger.warning(
                        f"Retriable error from {model_to_try.name} "
                        f"(attempt {attempt+1}): {e}"
                    )

                    # Smart retry decision: should we retry or skip to fallback?
                    if attempt < retry_config.max_attempts - 1:
                        should_retry = self.should_retry_error(
                            error=e,
                            model_config=model_to_try,
                            fallback_list=fallback_list,
                            current_model_idx=model_idx
                        )

                        if not should_retry:
                            # Skip retry, move to next fallback model
                            logger.info(
                                f"Smart retry: skipping further retries for {model_to_try.name}, "
                                f"will try next fallback model"
                            )
                            break

                    if attempt < retry_config.max_attempts - 1:
                        # Check if we have enough time for retry
                        elapsed_time = time.time() - fallback_start_time
                        remaining_time = total_timeout - elapsed_time

                        if remaining_time <= 0:
                            is_last_model = (model_idx == len(fallback_list) - 1)
                            if is_last_model:
                                logger.warning(
                                    f"Total timeout ({total_timeout}s) exceeded while retrying {model_to_try.name} "
                                    f"(last model in fallback list). All models have been attempted."
                                )
                            else:
                                logger.warning(
                                    f"Total timeout ({total_timeout}s) exceeded while retrying {model_to_try.name}. "
                                    f"Stopping retry and continuing to next model in fallback list."
                                )
                            break

                        # Calculate smart backoff delay (0 if healthy alternatives exist)
                        delay = self._calculate_backoff(
                            attempt=attempt,
                            model_config=model_to_try,
                            fallback_list=fallback_list,
                            current_model_idx=model_idx,
                            error=e
                        )

                        # Check if we have sufficient time after backoff for a meaningful request
                        time_after_backoff = remaining_time - delay

                        if time_after_backoff < MIN_USEFUL_TIMEOUT:
                            is_last_model = (model_idx == len(fallback_list) - 1)
                            if is_last_model:
                                logger.warning(
                                    f"After backoff ({delay:.1f}s), only {time_after_backoff:.1f}s remains, "
                                    f"which is less than minimum {MIN_USEFUL_TIMEOUT}s. "
                                    f"Last model in fallback list, stopping retry."
                                )
                            else:
                                logger.info(
                                    f"After backoff ({delay:.1f}s), only {time_after_backoff:.1f}s remains, "
                                    f"which is less than minimum {MIN_USEFUL_TIMEOUT}s. "
                                    f"Skipping retry, will try next fallback model."
                                )
                            break

                        # Adaptive backoff: don't let backoff consume too much time
                        # Limit backoff to 30% of remaining time (unless delay is 0)
                        if delay > 0:
                            adaptive_delay = min(delay, remaining_time * 0.3)
                            if adaptive_delay < delay:
                                logger.debug(
                                    f"Adaptive backoff: reduced from {delay:.1f}s to {adaptive_delay:.1f}s "
                                    f"(30% of remaining {remaining_time:.1f}s)"
                                )
                                delay = adaptive_delay

                        if delay > 0:
                            logger.info(f"Retrying after {delay:.1f}s backoff...")
                            time.sleep(delay)
                        else:
                            logger.info("Immediate retry to healthy alternative (0s backoff)")
                    else:
                        # Max retries reached, mark unhealthy and try fallback
                        if METRICS_AVAILABLE:
                            retry_exhausted_total.labels(model=model_to_try.name).inc()

                        # Only mark unhealthy if actual_request check is enabled
                        if self.health_checker._should_mark_unhealthy_on_user_request_failure(model_to_try):
                            self.health_checker.record_failure(
                                model_to_try,
                                str(e),
                                check_type="actual_request"
                            )
                        logger.error(
                            f"Model {model_to_try.name} failed after {retry_config.max_attempts} retries"
                        )
                        break  # Move to next model in fallback list

                except NonRetriableError as e:
                    # Non-retriable error: immediately move to fallback
                    duration = time.time() - start_time
                    if METRICS_AVAILABLE:
                        model_request_total.labels(
                            model=model_to_try.name,
                            status="non_retriable_error"
                        ).inc()
                        model_request_duration_seconds.labels(
                            model=model_to_try.name
                        ).observe(duration)

                    logger.error(
                        f"Non-retriable error from {model_to_try.name}: {e}"
                    )
                    # Only mark unhealthy if actual_request check is enabled
                    if self.health_checker._should_mark_unhealthy_on_user_request_failure(model_to_try):
                        self.health_checker.record_failure(
                            model_to_try,
                            str(e),
                            check_type="actual_request"
                        )
                    break  # Move to next model in fallback list

                except Exception as e:
                    # Unknown error: treat as non-retriable
                    duration = time.time() - start_time
                    if METRICS_AVAILABLE:
                        model_request_total.labels(
                            model=model_to_try.name,
                            status="non_retriable_error"
                        ).inc()
                        model_request_duration_seconds.labels(
                            model=model_to_try.name
                        ).observe(duration)

                    logger.error(
                        f"Unknown error from {model_to_try.name}: {e}",
                        exc_info=True
                    )
                    # Only mark unhealthy if actual_request check is enabled
                    if self.health_checker._should_mark_unhealthy_on_user_request_failure(model_to_try):
                        self.health_checker.record_failure(
                            model_to_try,
                            str(e),
                            check_type="actual_request"
                        )
                    break  # Move to next model in fallback list

        logger.warning(
            f"All {len(fallback_list)} models in fallback list have been attempted. "
            f"Attempted models: {attempted_models}"
        )

        # All models failed
        if METRICS_AVAILABLE:
            all_models_failed_total.inc()

        raise AllModelsFailed(attempted_models)

    def reload_config(self) -> bool:
        """Reload configuration from file and update health checker"""
        result = self.config_manager.reload_config()
        if result:
            # Notify health checker of config update
            self.health_checker.update_config({})
            logger.info("Configuration reloaded and health checker updated")
        return result


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