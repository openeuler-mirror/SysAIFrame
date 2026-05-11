"""
Copyright (C) 2025 CTyunOS. All Rights Reserved.
File: cli/utils/output.py
Desc: CLI output formatting utilities
Date: 2025-11-27
Author: Liu Mingran
"""

import click
import json
from typing import Any, Dict, List, Optional


class Output:
    """CLI output formatting utilities"""

    # Exit codes (kept for backward compatibility)
    EXIT_SUCCESS = 0
    EXIT_CONFIG_NOT_FOUND = 1
    EXIT_PERMISSION_DENIED = 2
    EXIT_VALIDATION_ERROR = 3
    EXIT_DUPLICATE_ID = 4
    EXIT_WRITE_FAILED = 5
    EXIT_LOCK_TIMEOUT = 6
    EXIT_VERSION_CONFLICT = 7
    EXIT_SERVICE_NOT_RUNNING = 8
    EXIT_DBUS_ERROR = 9
