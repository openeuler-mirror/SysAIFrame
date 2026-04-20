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

    @property
    def is_warning(self) -> bool:
        """Whether this is a warning status"""
        return self.level == StatusLevel.WARNING

    @property
    def is_info(self) -> bool:
        """Whether this is an info status"""
        return self.level == StatusLevel.INFO

    def __str__(self) -> str:
        """String representation"""
        return f"[{self.code}:{self.name}]"

    def __repr__(self) -> str:
        """Detailed representation"""
        return f"StatusCode(code={self.code}, name={self.name}, level={self.level.value})"


# ========== Success Status (0-999) ==========
SUCCESS = StatusCode(
    0, "SUCCESS", "Operation completed successfully",
    StatusLevel.SUCCESS, 200, 0
)

CREATED = StatusCode(
    1, "CREATED", "Resource created successfully",
    StatusLevel.SUCCESS, 201, 0
)

UPDATED = StatusCode(
    2, "UPDATED", "Resource updated successfully",
    StatusLevel.SUCCESS, 200, 0
)

DELETED = StatusCode(
    3, "DELETED", "Resource deleted successfully",
    StatusLevel.SUCCESS, 200, 0
)

CONFIG_RELOADED = StatusCode(
    4, "CONFIG_RELOADED", "Configuration reloaded successfully",
    StatusLevel.SUCCESS, 200, 0
)


# ========== Info Status (1000-1999) ==========
OPERATION_PENDING = StatusCode(
    1001, "OPERATION_PENDING", "Operation pending",
    StatusLevel.INFO, 202, 0
)

PARTIAL_SUCCESS = StatusCode(
    1002, "PARTIAL_SUCCESS", "Partial success: {details}",
    StatusLevel.INFO, 207, 0
)

NO_CHANGE = StatusCode(
    1003, "NO_CHANGE", "No changes needed",
    StatusLevel.INFO, 200, 0
)


# ========== Warning Status (2000-2999) ==========
DEPRECATION_WARNING = StatusCode(
    2001, "DEPRECATION_WARNING", "Feature deprecated: {details}",
    StatusLevel.WARNING, 200, 0
)

CONFIG_FALLBACK = StatusCode(
    2002, "CONFIG_FALLBACK", "Config loading failed, using default configuration",
    StatusLevel.WARNING, 200, 0
)

MODEL_UNHEALTHY = StatusCode(
    2003, "MODEL_UNHEALTHY", "Model unhealthy: {model}",
    StatusLevel.WARNING, 200, 0
)

SERVICE_DEGRADED = StatusCode(
    2004, "SERVICE_DEGRADED", "Service running in degraded mode: {reason}",
    StatusLevel.WARNING, 503, 0
)

FORCE_OVERWRITE = StatusCode(
    2005, "FORCE_OVERWRITE", "Force overwriting existing resource",
    StatusLevel.WARNING, 200, 0
)


# ========== Configuration Errors (3000-3999) ==========
CONFIG_NOT_FOUND = StatusCode(
    3001, "CONFIG_NOT_FOUND", "Configuration file not found: {path}",
    StatusLevel.ERROR, 404, 1
)

CONFIG_INVALID = StatusCode(
    3002, "CONFIG_INVALID", "Invalid configuration: {details}",
    StatusLevel.ERROR, 400, 3
)

CONFIG_PERMISSION_DENIED = StatusCode(
    3003, "CONFIG_PERMISSION_DENIED", "Permission denied: {path}",
    StatusLevel.ERROR, 403, 2
)
