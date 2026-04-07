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
