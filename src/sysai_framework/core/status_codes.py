"""
Copyright (C) 2025 CTyunOS. All Rights Reserved.
File: status_codes.py
Desc: Unified status code system - using dataclass to define all operation statuses
Date: 2025-11-28
Author: Liu Mingran
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Any, Dict


class StatusLevel(Enum):
    """Status level enumeration"""
    SUCCESS = "success"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"
