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
