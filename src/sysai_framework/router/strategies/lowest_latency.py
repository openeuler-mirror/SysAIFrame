"""
Copyright (C) 2025 CTyunOS. All Rights Reserved.
File: strategies/lowest_latency.py
Desc: Lowest latency load balance strategy - selects model with lowest average latency
Date: 2025-01-26
Author: Liu Mingran
"""

import threading
from typing import List, Optional, Dict
from collections import deque

from sysai_framework.config.model_config import ModelConfig
from sysai_framework.router.routing_strategy import BaseRoutingStrategy

import logging

logger = logging.getLogger(__name__)


class LowestLatencyStrategy(BaseRoutingStrategy):
    """Lowest latency load balance strategy - selects model with lowest average latency"""

    def __init__(self, config_manager=None):
        super().__init__(config_manager)
        self._latency_history: Dict[str, deque] = {}
        self._lock = threading.Lock()

        if config_manager:
            runtime_config = config_manager.routing_config.runtime
            self._latency_window = runtime_config.load_balance.options.latency_window
            self._latency_buffer = runtime_config.load_balance.options.latency_buffer
        else:
            self._latency_window = 10
            self._latency_buffer = 0.1

    def select_deployment(
        self,
        healthy_models: List[ModelConfig]
    ) -> Optional[ModelConfig]:
        """
        Select model with lowest average latency

        Args:
            healthy_models: List of healthy ModelConfig instances

        Returns:
            Selected ModelConfig or None if no models available
        """
        if not healthy_models:
            return None

        with self._lock:
            latencies = []
            for model in healthy_models:
                history = self._latency_history.get(model.instance_id, deque())
                if len(history) > 0:
                    avg_latency = sum(history) / len(history)
                else:
                    avg_latency = float('inf')
                latencies.append((model, avg_latency))

            latencies.sort(key=lambda x: x[1])

            if not latencies:
                return None

            min_latency = latencies[0][1]
            if min_latency == float('inf'):
                selected = healthy_models[0]
            else:
                max_allowed_latency = min_latency * (1 + self._latency_buffer)
                candidates = [
                    (model, latency) for model, latency in latencies
                    if latency <= max_allowed_latency
                ]
                import random
                selected = random.choice(candidates)[0] if candidates else latencies[0][0]

            logger.debug(
                f"Lowest-latency selected: {selected.name} "
                f"(instance_id={selected.instance_id}, avg_latency={latencies[0][1]:.3f}s)"
            )
            return selected

    def log_success(
        self,
        model_config: ModelConfig,
        response_time: float,
        tokens_used: int = 0
    ) -> None:
        """Record latency on success"""
        with self._lock:
            if model_config.instance_id not in self._latency_history:
                self._latency_history[model_config.instance_id] = deque(maxlen=self._latency_window)

            self._latency_history[model_config.instance_id].append(response_time)

            if len(self._latency_history[model_config.instance_id]) > self._latency_window:
                self._latency_history[model_config.instance_id].popleft()
