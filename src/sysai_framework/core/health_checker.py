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
