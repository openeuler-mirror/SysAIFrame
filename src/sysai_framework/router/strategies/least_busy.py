"""
Copyright (C) 2025 CTyunOS. All Rights Reserved.
File: strategies/least_busy.py
Desc: Least-busy load balance strategy - selects model with fewest active requests
Date: 2025-01-26
Author: Liu Mingran
"""

import threading
from typing import List, Optional, Dict

from sysai_framework.config.model_config import ModelConfig
from sysai_framework.router.routing_strategy import BaseRoutingStrategy

import logging

logger = logging.getLogger(__name__)


class LeastBusyStrategy(BaseRoutingStrategy):
    """Least-busy load balance strategy - selects model with fewest active requests"""

    def __init__(self, config_manager=None):
        super().__init__(config_manager)
        self._request_counts: Dict[str, int] = {}
        self._lock = threading.Lock()
