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
