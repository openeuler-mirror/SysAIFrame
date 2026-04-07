"""
Copyright (C) 2025 CTyunOS. All Rights Reserved.
File: routing_strategy.py
Desc: Load balance routing strategy base classes and enums
Date: 2025-01-26
Author: Liu Mingran
"""

from enum import Enum
from abc import ABC, abstractmethod
from typing import List, Optional
import logging

from sysai_framework.config.model_config import ModelConfig

logger = logging.getLogger(__name__)


class RuntimeMode(Enum):
    """Runtime mode enumeration"""
    DEFAULT = "default"
    LOAD_BALANCE = "load-balance"


class LoadBalanceStrategy(Enum):
    """Load balance strategy enumeration"""
    ROUND_ROBIN = "round-robin"
    WEIGHTED = "weighted"
    LEAST_BUSY = "least-busy"
    LOWEST_LATENCY = "lowest-latency"
    USAGE_BASED = "usage-based"


class BaseRoutingStrategy(ABC):
    """Base class for load balance routing strategies"""

    def __init__(self, config_manager=None):
        """
        Initialize routing strategy

        Args:
            config_manager: ModelConfigManager instance for accessing configuration
        """
        self.config_manager = config_manager
