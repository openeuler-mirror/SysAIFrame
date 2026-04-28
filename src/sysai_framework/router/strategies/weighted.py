"""
Copyright (C) 2025 CTyunOS. All Rights Reserved.
File: strategies/weighted.py
Desc: Weighted random load balance strategy
Date: 2025-01-26
Author: Liu Mingran
"""

import random
from typing import List, Optional

from sysai_framework.config.model_config import ModelConfig
from sysai_framework.router.routing_strategy import BaseRoutingStrategy

import logging

logger = logging.getLogger(__name__)


class WeightedStrategy(BaseRoutingStrategy):
    """Weighted random load balance strategy - selects based on weight"""
    pass
