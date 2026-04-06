"""
Copyright (C) 2025 CTyunOS. All Rights Reserved.
File: hooks.py
Desc: Hook system for SysAIFrame
     Extensible hook mechanism for request processing lifecycle
Date: 2025-10-22
Author: Liu Mingran
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List, Callable
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class BaseHook(ABC):
    """Base hook class - all hooks must inherit from this"""

    def __init__(self, name: Optional[str] = None):
        """
        Initialize hook

        Args:
            name: Optional name for the hook (for logging)
        """
        self.name = name or self.__class__.__name__
        self.enabled = True
