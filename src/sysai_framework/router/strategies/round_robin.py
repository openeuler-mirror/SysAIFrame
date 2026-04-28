"""
Copyright (C) 2025 CTyunOS. All Rights Reserved.
File: strategies/round_robin.py
Desc: Round-robin load balance strategy
Date: 2025-01-26
Author: Liu Mingran
"""

import threading
from typing import List, Optional

from sysai_framework.config.model_config import ModelConfig
from sysai_framework.router.routing_strategy import BaseRoutingStrategy

import logging

logger = logging.getLogger(__name__)


class RoundRobinStrategy(BaseRoutingStrategy):
    """Round-robin load balance strategy - cycles through models in order"""

    def __init__(self, config_manager=None):
        super().__init__(config_manager)
        self._index = 0
        self._lock = threading.Lock()
