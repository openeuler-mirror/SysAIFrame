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


@dataclass(frozen=True)
class StatusCode:
    """
    Unified status code definition

    Uses dataclass to define status codes, providing type safety and clear semantics.
    Each status code contains: numeric code, name, message template, level, HTTP status code, and CLI exit code.

    Attributes:
        code: Numeric status code (unique identifier)
        name: Status code name (string identifier for logging and debugging)
        message_template: Message template (supports format parameters)
        level: Status level (SUCCESS/INFO/WARNING/ERROR/CRITICAL)
        http_status: Corresponding HTTP status code
        cli_exit_code: Corresponding CLI exit code
    """
    code: int
    name: str
    message_template: str
    level: StatusLevel
    http_status: int = 200
    cli_exit_code: int = 0

    @property
    def is_success(self) -> bool:
        """Whether this is a success status"""
        return self.level == StatusLevel.SUCCESS

    @property
    def is_error(self) -> bool:
        """Whether this is an error status (includes ERROR and CRITICAL)"""
        return self.level in (StatusLevel.ERROR, StatusLevel.CRITICAL)
