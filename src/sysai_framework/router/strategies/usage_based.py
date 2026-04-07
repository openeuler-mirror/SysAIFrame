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
    pass
