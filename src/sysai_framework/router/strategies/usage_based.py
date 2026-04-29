"""
Copyright (C) 2025 CTyunOS. All Rights Reserved.
File: strategies/usage_based.py
Desc: Usage-based load balance strategy - selects model with lowest TPM/RPM usage
Date: 2025-01-26
Author: Liu Mingran
"""

import threading
import time
from typing import List, Optional, Dict, Tuple

from sysai_framework.config.model_config import ModelConfig
from sysai_framework.router.routing_strategy import BaseRoutingStrategy

import logging

logger = logging.getLogger(__name__)


class UsageBasedStrategy(BaseRoutingStrategy):
    """Usage-based load balance strategy - selects model with lowest TPM/RPM usage"""

    def __init__(self, config_manager=None):
        super().__init__(config_manager)
        # Track usage per model instance_id
        # Format: instance_id -> list of (timestamp, tokens, is_request)
        self._usage_history: Dict[str, List[Tuple[float, int, bool]]] = {}
        self._lock = threading.Lock()

        # Get usage window from config
        if config_manager:
            runtime_config = config_manager.routing_config.runtime
            self._usage_window = runtime_config.load_balance.options.usage_window
        else:
            self._usage_window = 60  # Default: 60 seconds

    def _cleanup_old_records(self, instance_id: str, current_time: float) -> None:
        """Remove usage records older than usage_window"""
        if instance_id not in self._usage_history:
            return

        cutoff_time = current_time - self._usage_window
        self._usage_history[instance_id] = [
            (ts, tokens, is_req) for ts, tokens, is_req in self._usage_history[instance_id]
            if ts >= cutoff_time
        ]

    def _calculate_usage(self, instance_id: str, current_time: float) -> Tuple[int, int]:
        """
        Calculate TPM and RPM for a model

        Returns:
            Tuple of (tpm, rpm)
        """
        if instance_id not in self._usage_history:
            return (0, 0)

        self._cleanup_old_records(instance_id, current_time)

        history = self._usage_history[instance_id]
        if not history:
            return (0, 0)

        # Calculate TPM (tokens per minute) and RPM (requests per minute)
        # Scale to per-minute from usage_window
        tokens = sum(tokens for _, tokens, _ in history)
        requests = sum(1 for _, _, is_req in history if is_req)

        # Scale to per-minute
        scale_factor = 60.0 / self._usage_window
        tpm = int(tokens * scale_factor)
        rpm = int(requests * scale_factor)

        return (tpm, rpm)

    def select_deployment(
        self,
        healthy_models: List[ModelConfig]
    ) -> Optional[ModelConfig]:
        """
        Select model with lowest usage (TPM + RPM)

        Args:
            healthy_models: List of healthy ModelConfig instances

        Returns:
            Selected ModelConfig or None if no models available
        """
        if not healthy_models:
            return None

        current_time = time.time()

        with self._lock:
            # Calculate usage for each model
            usages = []
            for model in healthy_models:
                tpm, rpm = self._calculate_usage(model.instance_id, current_time)
                # Combined usage score (can be customized)
                usage_score = tpm + rpm * 100  # Weight requests more
                usages.append((model, usage_score, tpm, rpm))

            # Sort by usage score (ascending)
            usages.sort(key=lambda x: x[1])

            # Select model with minimum usage
            selected = usages[0][0]

            logger.debug(
                f"Usage-based selected: {selected.name} "
                f"(instance_id={selected.instance_id}, tpm={usages[0][2]}, rpm={usages[0][3]})"
            )
            return selected

    def log_success(
        self,
        model_config: ModelConfig,
        response_time: float,
        tokens_used: int = 0
    ) -> None:
        """Record usage on success"""
        current_time = time.time()

        with self._lock:
            if model_config.instance_id not in self._usage_history:
                self._usage_history[model_config.instance_id] = []

            # Record tokens used
            if tokens_used > 0:
                self._usage_history[model_config.instance_id].append(
                    (current_time, tokens_used, False)
                )

            # Record request
            self._usage_history[model_config.instance_id].append(
                (current_time, 0, True)
            )

            # Cleanup old records
            self._cleanup_old_records(model_config.instance_id, current_time)

