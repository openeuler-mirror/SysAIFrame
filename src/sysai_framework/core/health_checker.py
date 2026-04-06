"""
Copyright (C) 2025 CTyunOS. All Rights Reserved.
File: health_checker.py
Desc: Health checker for model instances
Date: 2026-01-16
Author: Liu Mingran
"""

import threading
import time
import queue
import requests
import logging
from datetime import datetime
from typing import Dict, Optional, Any, TYPE_CHECKING, Tuple

if TYPE_CHECKING:
    from sysai_framework.config.model_config import ModelConfig, ModelConfigManager

from sysai_framework.config.model_config import UnhealthyReason
from sysai_framework.llms.http_handler import get_http_handler
from sysai_framework.utils.provider_utils import get_llm_provider
from sysai_framework.llms.base.transformation import BaseConfig

# Import metrics
try:
    from sysai_framework.core.metrics import (
        health_check_total,
        health_check_success,
        health_check_failure,
        health_check_duration_seconds,
        model_healthy_status,
        model_consecutive_failures,
        model_consecutive_successes,
        model_unhealthy_reason
    )
    METRICS_AVAILABLE = True
except ImportError:
    METRICS_AVAILABLE = False

logger = logging.getLogger(__name__)

# Lightweight check failure threshold (consecutive failures before marking unhealthy)
LIGHTWEIGHT_FAILURE_THRESHOLD = 2

# Health stats lock acquisition timeout (avoid API blocking on stuck locks)
HEALTH_STATS_LOCK_TIMEOUT_SECONDS = 0.2

# Max queued health-changed signals (drop on overflow)
HEALTH_SIGNAL_QUEUE_MAXSIZE = 1024


class HealthChecker:
    """
    Health checker for model instances

    Provides:
    - Lightweight health checks (HTTP HEAD requests) - checks connection_health
    - Actual request validation (test messages) - checks overall is_healthy
    - Separate background threads for lightweight and actual request checks
    - Synchronous health status updates on model calls
    - Differentiated recovery based on connection_health and is_healthy
    - Dual health flags: connection_health (connection layer) and is_healthy (overall)
    """

    def __init__(self, config_manager: 'ModelConfigManager'):
        """
        Initialize health checker

        Args:
            config_manager: Model configuration manager instance
        """
        self.config_manager = config_manager
        self._lightweight_running = False
        self._lightweight_thread: Optional[threading.Thread] = None
        self._lightweight_config_event = threading.Event()  # Signal for config updates
        self._actual_request_running = False
        self._actual_request_thread: Optional[threading.Thread] = None
        self._actual_request_config_event = threading.Event()  # Signal for config updates
        self._thread_management_lock = threading.Lock()  # Protect thread start/stop operations

        # D-Bus signal dispatching (decouple from health locks / worker threads)
        self._signal_queue: "queue.Queue[Tuple[str, str, bool, str]]" = queue.Queue(
            maxsize=HEALTH_SIGNAL_QUEUE_MAXSIZE
        )
        self._signal_dispatch_running = True
        self._signal_dispatch_thread = threading.Thread(
            target=self._signal_dispatch_loop,
            daemon=True,
            name="HealthSignalDispatch"
        )
        self._signal_dispatch_thread.start()

        logger.debug("HealthChecker initialized")

    # === Concurrent-safe state updates (simplified: fail once -> unhealthy, success once -> recover) ===

    def record_success(self, model_config: 'ModelConfig', check_type: str = "lightweight"):
        """
        Record successful health check (atomic operation)

        Args:
            model_config: Model configuration
            check_type: Check type ("lightweight" or "actual_request")
        """
        # Update metrics
        if METRICS_AVAILABLE:
            health_check_success.labels(model=model_config.name, check_type=check_type).inc()

        should_recover = False
        was_unhealthy_reason: Optional[str] = None
        model_name = model_config.name
        instance_id = str(model_config.instance_id)

        with model_config._health_lock:
            model_config.consecutive_successes += 1
            model_config.consecutive_failures = 0  # Reset failure count
            model_config.last_health_check = datetime.now()

            # Update Prometheus gauges
            if METRICS_AVAILABLE:
                model_consecutive_successes.labels(
                    model=model_config.name,
                    instance_id=model_config.instance_id
                ).set(model_config.consecutive_successes)
                model_consecutive_failures.labels(
                    model=model_config.name,
                    instance_id=model_config.instance_id
                ).set(model_config.consecutive_failures)

            # Update connection_health for lightweight checks
            if check_type == "lightweight":
                previous_connection_health = model_config.connection_health
                model_config.connection_health = True
            else:
                previous_connection_health = model_config.connection_health

            # Recovery logic: simplified based on connection_health and is_healthy
            if not model_config.is_healthy:
                can_recover = False

                # If connection_health is False, only lightweight success can recover connection_health
                if not previous_connection_health:
                    if check_type == "lightweight":
                        can_recover = True
                elif model_config.connection_health and check_type == "actual_request":
                    can_recover = True

                if can_recover:
                    was_unhealthy_reason = model_config.unhealthy_reason.value
                    should_recover = True
                else:
                    logger.debug(
                        f"Model {model_config.name} check succeeded ({check_type}), "
                        f"but cannot recover (connection_health={model_config.connection_health}, "
                        f"unhealthy_reason={model_config.unhealthy_reason.value})"
                    )

        # Recover and emit outside lock to avoid deadlocks/blocking
        if should_recover:
            self.mark_healthy(model_config)
            logger.info(
                f"Model {model_name} recovered to healthy "
                f"(check_type={check_type}, was {was_unhealthy_reason})"
            )
            self._enqueue_health_changed_signal(model_name, instance_id, True, "")

    def record_failure(self, model_config: 'ModelConfig', error_msg: Optional[str] = None,
                      check_type: str = "lightweight"):
        """
        Record failed health check (atomic operation) - fail once -> immediately unhealthy

        Args:
            model_config: Model configuration
            error_msg: Error message
            check_type: Check type ("lightweight" or "actual_request")
        """
        # Update metrics
        if METRICS_AVAILABLE:
            health_check_failure.labels(model=model_config.name, check_type=check_type).inc()

        emit_signal: Optional[Tuple[str, str, bool, str]] = None
        model_name = model_config.name
        instance_id = str(model_config.instance_id)

        with model_config._health_lock:
            model_config.consecutive_failures += 1
            model_config.consecutive_successes = 0  # Reset success count
            model_config.last_health_check = datetime.now()

            # Update Prometheus gauges
            if METRICS_AVAILABLE:
                model_consecutive_failures.labels(
                    model=model_config.name,
                    instance_id=model_config.instance_id
                ).set(model_config.consecutive_failures)
                model_consecutive_successes.labels(
                    model=model_config.name,
                    instance_id=model_config.instance_id
                ).set(model_config.consecutive_successes)

            # Handle failure based on check type
            if check_type == "lightweight":
                # If lightweight check is disabled, don't update connection_health
                if not self._is_lightweight_enabled():
                    logger.debug(
                        f"Lightweight check failed for {model_config.name}, "
                        f"but lightweight check is disabled, skipping connection_health update"
                    )
                    return

                # Lightweight check failure: use threshold before marking unhealthy
                if model_config.consecutive_failures >= LIGHTWEIGHT_FAILURE_THRESHOLD:
                    # Mark connection_health as False, which forces is_healthy=False
                    model_config.connection_health = False
                    if model_config.is_healthy:
                        reason = UnhealthyReason.LIGHTWEIGHT_CHECK_FAILED
                        self._mark_unhealthy_internal(model_config, reason)
                        logger.error(
                            f"Model {model_config.name} marked as unhealthy "
                            f"(check_type={check_type}, reason={reason.value}, error={error_msg})"
                        )
                        emit_signal = (model_name, instance_id, False, reason.value)
                    else:
                        # Already unhealthy, but update reason if needed
                        if model_config.unhealthy_reason != UnhealthyReason.LIGHTWEIGHT_CHECK_FAILED:
                            model_config.unhealthy_reason = UnhealthyReason.LIGHTWEIGHT_CHECK_FAILED
                else:
                    # Not enough failures yet, just log
                    logger.debug(
                        f"Model {model_config.name} lightweight check failed "
                        f"({model_config.consecutive_failures}/{LIGHTWEIGHT_FAILURE_THRESHOLD}), "
                        f"not marking unhealthy yet"
                    )
            else:
                # Actual request failure: mark unhealthy immediately (if was healthy)
                if model_config.is_healthy and model_config.connection_health:
                    reason = UnhealthyReason.ACTUAL_REQUEST_FAILED
                    self._mark_unhealthy_internal(model_config, reason)
                    logger.error(
                        f"Model {model_config.name} marked as unhealthy "
                        f"(check_type={check_type}, reason={reason.value}, error={error_msg})"
                    )
                    emit_signal = (model_name, instance_id, False, reason.value)
                elif not model_config.connection_health:
                    # Connection health is False, so is_healthy should already be False
                    pass

        # Emit outside lock to avoid blocking health state updates / API reads
        if emit_signal:
            self._enqueue_health_changed_signal(*emit_signal)

    def mark_unhealthy(self, model_config: 'ModelConfig',
                      reason: UnhealthyReason = UnhealthyReason.ACTUAL_REQUEST_FAILED):
        """
        Immediately mark as unhealthy (called externally, e.g., on Fallback)

        Args:
            model_config: Model configuration
            reason: Unhealthy reason
        """
        with model_config._health_lock:
            was_healthy = model_config.is_healthy
            # If reason is LIGHTWEIGHT_CHECK_FAILED, also set connection_health=False
            if reason == UnhealthyReason.LIGHTWEIGHT_CHECK_FAILED:
                model_config.connection_health = False
            self._mark_unhealthy_internal(model_config, reason)

        # Emit D-Bus signal outside lock if status changed
        if was_healthy:
            self._enqueue_health_changed_signal(
                model_config.name,
                str(model_config.instance_id),
                False,
                reason.value
            )

    def mark_healthy(self, model_config: 'ModelConfig'):
        """
        Immediately mark as healthy (recovery)

        Args:
            model_config: Model configuration
        """
        with model_config._health_lock:
            model_config.is_healthy = True
            # Ensure connection_health is True when marking healthy
            model_config.connection_health = True
            model_config.unhealthy_reason = UnhealthyReason.NONE  # Clear unhealthy reason
            model_config.consecutive_failures = 0

            # Update Prometheus metrics
            if METRICS_AVAILABLE:
                model_healthy_status.labels(
                    model=model_config.name,
                    instance_id=model_config.instance_id
                ).set(1)
                model_unhealthy_reason.labels(
                    model=model_config.name,
                    instance_id=model_config.instance_id
                ).set(0)

    def _emit_health_changed_signal_by_fields(
        self,
        model_name: str,
        instance_id: str,
        is_healthy: bool,
        reason: str
    ):
        """
        Emit D-Bus signal when model health status changes.

        Args:
            model_name: Model name
            instance_id: Model instance id
            is_healthy: Current health status
            reason: Unhealthy reason (empty string if healthy)
        """
        try:
            from sysai_framework.dbus_service import get_admin_service

            admin_service = get_admin_service()
            if admin_service:
                admin_service.emit_model_health_changed(
                    model_name,
                    instance_id,
                    is_healthy,
                    reason
                )
        except Exception as e:
            # Don't let D-Bus signal failures disrupt health checking
            logger.debug(f"Failed to emit health changed signal: {e}")

    def _emit_health_changed_signal(self, model_config: 'ModelConfig',
                                    is_healthy: bool, reason: str):
        """Backward-compatible wrapper (kept for internal callers)."""
        self._emit_health_changed_signal_by_fields(
            model_config.name,
            str(model_config.instance_id),
            is_healthy,
            reason
        )

    def _enqueue_health_changed_signal(
        self,
        model_name: str,
        instance_id: str,
        is_healthy: bool,
        reason: str
    ) -> None:
        """Enqueue health-changed signal for async dispatch (drop if queue is full)."""
        try:
            self._signal_queue.put_nowait((model_name, instance_id, is_healthy, reason))
        except queue.Full:
            logger.debug(
                "Health signal queue full, dropping signal: "
                f"model={model_name}, instance_id={instance_id}, healthy={is_healthy}, reason={reason}"
            )
        except Exception as e:
            logger.debug(f"Failed to enqueue health changed signal: {e}")

    def _signal_dispatch_loop(self) -> None:
        """Dispatch queued health-changed signals in a dedicated thread."""
        while self._signal_dispatch_running:
            try:
                item = self._signal_queue.get(timeout=1.0)
            except queue.Empty:
                continue
            except Exception as e:
                logger.debug(f"Health signal dispatcher queue error: {e}")
                continue

            try:
                model_name, instance_id, is_healthy, reason = item
                self._emit_health_changed_signal_by_fields(model_name, instance_id, is_healthy, reason)
            except Exception as e:
                logger.debug(f"Health signal dispatch failed: {e}")
            finally:
                try:
                    self._signal_queue.task_done()
                except Exception:
                    pass

    def _mark_unhealthy_internal(self, model_config: 'ModelConfig', reason: UnhealthyReason):
        """
        Internal method: mark unhealthy

        Args:
            model_config: Model configuration
            reason: Unhealthy reason
        """
        model_config.is_healthy = False
        model_config.unhealthy_reason = reason

        # Ensure connection_health=False when reason is LIGHTWEIGHT_CHECK_FAILED
        if reason == UnhealthyReason.LIGHTWEIGHT_CHECK_FAILED:
            model_config.connection_health = False

        # Update Prometheus metrics
        if METRICS_AVAILABLE:
            model_healthy_status.labels(
                model=model_config.name,
                instance_id=model_config.instance_id
            ).set(0)

            # Encode unhealthy reason as number
            reason_code = 0
            if reason == UnhealthyReason.LIGHTWEIGHT_CHECK_FAILED:
                reason_code = 1
            elif reason == UnhealthyReason.ACTUAL_REQUEST_FAILED:
                reason_code = 2

            model_unhealthy_reason.labels(
                model=model_config.name,
                instance_id=model_config.instance_id
            ).set(reason_code)

    # === Health check methods ===

    def check_endpoint_lightweight(self, model_config: 'ModelConfig') -> bool:
        """
        Lightweight health check (HTTP HEAD request)

        Args:
            model_config: Model configuration

        Returns:
            True if healthy, False otherwise
        """
        if not model_config.api_base:
            # No API base, cannot check (e.g., mock models)
            return True

        # Update metrics
        if METRICS_AVAILABLE:
            health_check_total.labels(model=model_config.name, check_type="lightweight").inc()

        start_time = time.time()
        try:
            timeout = self._get_timeout()
            response = requests.head(model_config.api_base, timeout=timeout)
            success = response.status_code < 500

            duration = time.time() - start_time
            if METRICS_AVAILABLE:
                health_check_duration_seconds.labels(
                    model=model_config.name,
                    check_type="lightweight"
                ).observe(duration)

            if success:
                self.record_success(model_config, check_type="lightweight")
                logger.debug(f"Lightweight check passed for {model_config.name}")
            else:
                self.record_failure(
                    model_config,
                    f"HTTP {response.status_code}",
                    check_type="lightweight"
                )

            return success

        except requests.RequestException as e:
            if METRICS_AVAILABLE:
                duration = time.time() - start_time
                health_check_duration_seconds.labels(
                    model=model_config.name,
                    check_type="lightweight"
                ).observe(duration)
            self.record_failure(model_config, str(e), check_type="lightweight")
            logger.warning(f"Lightweight check failed for {model_config.name}: {e}")
            return False
        except Exception as e:
            if METRICS_AVAILABLE:
                duration = time.time() - start_time
                health_check_duration_seconds.labels(
                    model=model_config.name,
                    check_type="lightweight"
                ).observe(duration)
            self.record_failure(model_config, str(e), check_type="lightweight")
            logger.error(f"Unexpected error in lightweight check for {model_config.name}: {e}")
            return False

    def _get_provider_config(self, provider: str) -> Optional[BaseConfig]:
        """
        Get provider configuration class for health check

        Args:
            provider: Provider name (e.g., 'openai_like', 'dashscope', 'moonshot', 'deepseek')

        Returns:
            BaseConfig instance or None if not found
        """
        try:
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
        except ImportError as e:
            logger.warning(f"Failed to import provider config for {provider}: {e}")
            return None

    def check_model_actual_request(self, model_config: 'ModelConfig') -> bool:
        """
        Actual request validation (sends test message - incurs API costs)

        Uses http_handler instead of litellm to avoid external dependency.

        Args:
            model_config: Model configuration

        Returns:
            True if healthy, False otherwise
        """
        # Skip if API base is not configured (e.g., mock models)
        if not model_config.api_base:
            return True

        # Update metrics
        if METRICS_AVAILABLE:
            health_check_total.labels(model=model_config.name, check_type="actual_request").inc()

        start_time = time.time()
        try:
            # Get provider information
            actual_model, provider, api_key, api_base = get_llm_provider(
                model=model_config.name,
                custom_llm_provider=model_config.provider,
                api_base=model_config.api_base,
                api_key=model_config.api_key
            )

            # Get provider config
            provider_config = self._get_provider_config(provider)
            if not provider_config:
                logger.warning(f"Provider config not found for {provider}, skipping actual request check")
                if METRICS_AVAILABLE:
                    duration = time.time() - start_time
                    health_check_duration_seconds.labels(
                        model=model_config.name,
                        check_type="actual_request"
                    ).observe(duration)
                    health_check_failure.labels(
                        model=model_config.name,
                        check_type="actual_request"
                    ).inc()
                self.record_failure(
                    model_config,
                    f"Provider config not found for {provider}",
                    check_type="actual_request"
                )
                return False

            # Get HTTP handler
            http_handler = get_http_handler()

            # Prepare test request
            test_messages = [{"role": "user", "content": "hi"}]
            timeout = self._get_timeout()

            # Call model with minimal message using http_handler
            response = http_handler.completion(
                provider_config=provider_config,
                model=actual_model,
                messages=test_messages,
                api_base=api_base or model_config.api_base,
                api_key=api_key or model_config.api_key,
                optional_params={"max_tokens": 5},  # Minimize cost
                stream=False,
                timeout=timeout
            )

            duration = time.time() - start_time
            if METRICS_AVAILABLE:
                health_check_duration_seconds.labels(
                    model=model_config.name,
                    check_type="actual_request"
                ).observe(duration)

            # Check if response is valid
            success = (
                response and
                isinstance(response, dict) and
                'choices' in response and
                len(response.get('choices', [])) > 0
            )

            if success:
                self.record_success(model_config, check_type="actual_request")
                logger.debug(f"Actual request check passed for {model_config.name}")
            else:
                self.record_failure(
                    model_config,
                    "Invalid response format",
                    check_type="actual_request"
                )

            return success

        except Exception as e:
            duration = time.time() - start_time
            if METRICS_AVAILABLE:
                health_check_duration_seconds.labels(
                    model=model_config.name,
                    check_type="actual_request"
                ).observe(duration)
                health_check_failure.labels(
                    model=model_config.name,
                    check_type="actual_request"
                ).inc()

            self.record_failure(
                model_config,
                str(e),
                check_type="actual_request"
            )
            logger.warning(f"Actual request check failed for {model_config.name}: {e}")
            return False

    # === Background thread management ===

    def start_background_checks(self):
        """Start background health check threads"""
        with self._thread_management_lock:
            # Start lightweight check thread if enabled
            if self._is_lightweight_enabled() and not self._lightweight_running:
                self._lightweight_running = True
                self._lightweight_thread = threading.Thread(target=self._lightweight_check_loop, daemon=True)
                self._lightweight_thread.start()
                logger.debug("Health checker lightweight background thread started")

            # Start actual request check thread if enabled
            if self._is_actual_request_enabled_globally() and not self._actual_request_running:
                self._actual_request_running = True
                self._actual_request_thread = threading.Thread(target=self._actual_request_check_loop, daemon=True)
                self._actual_request_thread.start()
                logger.debug("Health checker actual request background thread started")

    def stop_background_checks(self):
        """Stop background threads"""
        with self._thread_management_lock:
            # Stop lightweight thread
            if self._lightweight_running:
                self._lightweight_running = False
                self._lightweight_config_event.set()  # Wake up thread if sleeping
                logger.debug("Health checker lightweight background thread stopping")

            # Stop actual request thread
            if self._actual_request_running:
                self._actual_request_running = False
                self._actual_request_config_event.set()  # Wake up thread if sleeping
                logger.debug("Health checker actual request background thread stopping")

    def _lightweight_check_loop(self):
        """
        Lightweight check loop (supports hot config updates)

        This method runs in a separate thread and performs periodic lightweight health checks.
        """
        logger.debug("Background lightweight health check loop started")

        while self._lightweight_running:
            try:
                # Get current configuration interval
                lightweight_interval = self._get_lightweight_interval()

                # Execute lightweight checks
                if self._is_lightweight_enabled():
                    self._check_all_models_lightweight()

                # Interruptible sleep (supports config hot updates)
                if self._lightweight_config_event.wait(timeout=lightweight_interval):
                    # Config has been updated, immediately use new config
                    self._lightweight_config_event.clear()
                    logger.debug("Lightweight health check config updated, applying new settings")

            except Exception as e:
                logger.error(f"Error in lightweight background health check loop: {e}", exc_info=True)
                # Sleep briefly before retrying
                time.sleep(5)

        logger.debug("Background lightweight health check loop stopped")

    def _actual_request_check_loop(self):
        """
        Actual request check loop (supports hot config updates)

        This method runs in a separate thread and performs periodic actual request health checks.
        """
        logger.debug("Background actual request health check loop started")

        while self._actual_request_running:
            try:
                # Get current configuration interval
                actual_request_interval = self._get_actual_request_interval()

                # Execute actual request validation (only if globally enabled)
                if self._is_actual_request_enabled_globally():
                    self._check_all_models_actual_request()

                # Interruptible sleep (supports config hot updates)
                if self._actual_request_config_event.wait(timeout=actual_request_interval):
                    # Config has been updated, immediately use new config
                    self._actual_request_config_event.clear()
                    logger.debug("Actual request health check config updated, applying new settings")

            except Exception as e:
                logger.error(f"Error in actual request background health check loop: {e}", exc_info=True)
                # Sleep briefly before retrying
                time.sleep(5)

        logger.debug("Background actual request health check loop stopped")

    def _check_all_models_lightweight(self):
        """Execute lightweight checks for all models"""
        for model_config in self.config_manager.models.values():
            if model_config.health_check_enabled:
                try:
                    self.check_endpoint_lightweight(model_config)
                except Exception as e:
                    logger.error(
                        f"Error checking model {model_config.name} (lightweight): {e}",
                        exc_info=True
                    )

    def _check_all_models_actual_request(self):
        """Execute actual request validation for all models with connection_health=True"""
        for model_config in self.config_manager.models.values():
            if model_config.health_check_enabled and model_config.connection_health:
                try:
                    self.check_model_actual_request(model_config)
                except Exception as e:
                    logger.error(
                        f"Error checking model {model_config.name} (actual request): {e}",
                        exc_info=True
                    )

    # === Config hot update ===

    def _reset_connection_health_for_all_models(self):
        """
        Reset connection_health for all models when lightweight check is disabled.
        This allows models that were marked as connection_health=False to be checked
        by actual request check and potentially recover.
        """
        reset_count = 0
        recovered_models = []

        for model_config in self.config_manager.models.values():
            if not model_config.health_check_enabled:
                continue

            with model_config._health_lock:
                was_unhealthy = not model_config.is_healthy
                was_lightweight_failure = (
                    model_config.unhealthy_reason == UnhealthyReason.LIGHTWEIGHT_CHECK_FAILED
                )

                # Reset connection_health
                if not model_config.connection_health:
                    model_config.connection_health = True
                    reset_count += 1

                # If model was unhealthy due to lightweight check failure, mark for recovery
                if was_unhealthy and was_lightweight_failure:
                    recovered_models.append(model_config)

        # Recover models outside the lock (mark_healthy acquires its own lock)
        for model_config in recovered_models:
            self.mark_healthy(model_config)
            self._enqueue_health_changed_signal(
                model_config.name,
                str(model_config.instance_id),
                True,
                ""
            )

        if reset_count > 0 or recovered_models:
            logger.info(
                f"Lightweight check disabled: reset connection_health for {reset_count} models, "
                f"recovered {len(recovered_models)} models from LIGHTWEIGHT_CHECK_FAILED"
            )

    def update_config(self, new_config: Dict[str, Any]):
        """
        Update health check configuration (hot update)

        Args:
            new_config: New health check configuration dict
        """
        # Update configuration in config manager
        logger.debug(f"Health check config update requested: {new_config}")

        # If lightweight_enabled is being set to False, reset connection_health for all models
        if 'lightweight_enabled' in new_config and not new_config['lightweight_enabled']:
            self._reset_connection_health_for_all_models()

        # Notify background threads
        self._lightweight_config_event.set()
        self._actual_request_config_event.set()

        # Manage threads based on configuration changes (with lock protection)
        with self._thread_management_lock:
            # Manage lightweight check thread
            lightweight_enabled = self._is_lightweight_enabled()
            if lightweight_enabled and not self._lightweight_running:
                # Configuration enabled but thread not running - start it
                self._lightweight_running = True
                self._lightweight_thread = threading.Thread(target=self._lightweight_check_loop, daemon=True)
                self._lightweight_thread.start()
                logger.info("Lightweight health check thread started")
            elif not lightweight_enabled and self._lightweight_running:
                # Configuration disabled but thread still running - stop it
                self._lightweight_running = False
                self._lightweight_config_event.set()  # Wake up thread
                logger.info("Lightweight health check thread will stop")

            # Manage actual request check thread
            actual_request_enabled = self._is_actual_request_enabled_globally()
            if actual_request_enabled and not self._actual_request_running:
                # Configuration enabled but thread not running - start it
                self._actual_request_running = True
                self._actual_request_thread = threading.Thread(target=self._actual_request_check_loop, daemon=True)
                self._actual_request_thread.start()
                logger.info("Actual request health check thread started")
            elif not actual_request_enabled and self._actual_request_running:
                # Configuration disabled but thread still running - stop it
                self._actual_request_running = False
                self._actual_request_config_event.set()  # Wake up thread
                logger.info("Actual request health check thread will stop")

        logger.debug("Health check config updated and applied")

    # === Configuration query helper methods ===

    def _is_actual_request_enabled_globally(self) -> bool:
        """Check if actual request validation is globally enabled"""
        return self.config_manager.routing_config.health_check.actual_request_enabled

    def _get_timeout(self) -> int:
        """Get health check timeout"""
        return self.config_manager.routing_config.health_check.timeout

    def _get_lightweight_interval(self) -> int:
        """Get lightweight check interval"""
        return self.config_manager.routing_config.health_check.lightweight_interval

    def _get_actual_request_interval(self) -> int:
        """Get actual request check interval"""
        return self.config_manager.routing_config.health_check.actual_request_interval

    def _is_lightweight_enabled(self) -> bool:
        """Check if lightweight checks are enabled"""
        return self.config_manager.routing_config.health_check.lightweight_enabled

    def _should_mark_unhealthy_on_user_request_failure(self, model_config: 'ModelConfig') -> bool:
        """
        Check if user request failure should mark model as unhealthy

        Args:
            model_config: Model configuration

        Returns:
            True if actual_request check is enabled globally, False otherwise
        """
        return self._is_actual_request_enabled_globally()

    # === Monitoring metrics ===

    def get_health_statistics(self) -> Dict[str, Any]:
        """
        Get health statistics for all models

        Returns:
            Dictionary with health statistics
        """
        pass










