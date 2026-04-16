"""
Copyright (C) 2025 CTyunOS. All Rights Reserved.
File: strategies/__init__.py
Desc: Load balance routing strategies
Date: 2025-01-26
Author: Liu Mingran
"""

from .round_robin import RoundRobinStrategy
from .weighted import WeightedStrategy
from .least_busy import LeastBusyStrategy
