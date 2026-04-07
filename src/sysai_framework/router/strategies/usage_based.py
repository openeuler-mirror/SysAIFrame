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
