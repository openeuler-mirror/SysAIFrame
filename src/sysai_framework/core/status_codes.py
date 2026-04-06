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

CONFIG_LOCKED = StatusCode(
    3004, "CONFIG_LOCKED", "Configuration file is locked",
    StatusLevel.ERROR, 423, 6
)

CONFIG_WRITE_FAILED = StatusCode(
    3005, "CONFIG_WRITE_FAILED", "Failed to write configuration: {details}",
    StatusLevel.ERROR, 500, 5
)


# ========== Model Errors (4000-4999) ==========
MODEL_NOT_FOUND = StatusCode(
    4001, "MODEL_NOT_FOUND", "Model not found: {model}",
    StatusLevel.ERROR, 404, 3
)

MODEL_ALREADY_EXISTS = StatusCode(
    4002, "MODEL_ALREADY_EXISTS", "Model already exists: {instance_id}",
    StatusLevel.ERROR, 409, 4
)

MODEL_INVALID = StatusCode(
    4003, "MODEL_INVALID", "Invalid model configuration: {details}",
    StatusLevel.ERROR, 400, 3
)

MODEL_UNAVAILABLE = StatusCode(
    4004, "MODEL_UNAVAILABLE", "Model unavailable: {model}",
    StatusLevel.ERROR, 503, 5
)


# ========== Connection and Network Errors (5000-5999) ==========
CONNECTION_ERROR = StatusCode(
    5001, "CONNECTION_ERROR", "Connection error: {details}",
    StatusLevel.ERROR, 503, 5
)

TIMEOUT_ERROR = StatusCode(
    5002, "TIMEOUT_ERROR", "Request timeout: {details}",
    StatusLevel.ERROR, 504, 6
)

NETWORK_ERROR = StatusCode(
    5003, "NETWORK_ERROR", "Network error: {details}",
    StatusLevel.ERROR, 503, 5
)

DISCONNECTED = StatusCode(
    5004, "DISCONNECTED", "Connection disconnected",
    StatusLevel.ERROR, 503, 5
)


# ========== D-Bus Errors (6000-6999) ==========
DBUS_NOT_AVAILABLE = StatusCode(
    6001, "DBUS_NOT_AVAILABLE", "D-Bus service not available",
    StatusLevel.ERROR, 503, 5
)

SERVICE_NOT_RUNNING = StatusCode(
    6002, "SERVICE_NOT_RUNNING", "Service not running",
    StatusLevel.ERROR, 503, 1
)

DBUS_CALL_FAILED = StatusCode(
    6003, "DBUS_CALL_FAILED", "D-Bus call failed: {details}",
    StatusLevel.ERROR, 500, 5
)


# ========== Validation Errors (7000-7999) ==========
VALIDATION_ERROR = StatusCode(
    7001, "VALIDATION_ERROR", "Validation failed: {details}",
    StatusLevel.ERROR, 400, 3
)

DUPLICATE_ID = StatusCode(
    7002, "DUPLICATE_ID", "Duplicate ID: {id}",
    StatusLevel.ERROR, 409, 4
)

INVALID_PARAMETER = StatusCode(
    7003, "INVALID_PARAMETER", "Invalid parameter: {param}",
    StatusLevel.ERROR, 400, 3
)


# ========== Stream Processing Errors (8000-8999) ==========
STREAM_ERROR = StatusCode(
    8001, "STREAM_ERROR", "Stream processing error: {details}",
    StatusLevel.ERROR, 500, 5
)

STREAM_INTERRUPTED = StatusCode(
    8002, "STREAM_INTERRUPTED", "Stream interrupted",
    StatusLevel.ERROR, 499, 5
)


# ========== System Errors (9000-9999) ==========
INTERNAL_ERROR = StatusCode(
    9001, "INTERNAL_ERROR", "Internal error: {details}",
    StatusLevel.CRITICAL, 500, 1
)

NOT_IMPLEMENTED = StatusCode(
    9002, "NOT_IMPLEMENTED", "Feature not implemented",
    StatusLevel.ERROR, 501, 1
)

UNKNOWN_ERROR = StatusCode(
    9999, "UNKNOWN_ERROR", "Unknown error: {details}",
    StatusLevel.CRITICAL, 500, 1
)


@dataclass
class OperationResult:
    """
    Operation result wrapper class - unified wrapper for all operation results

    Used to replace traditional (bool, str, data) tuple return values, providing clearer semantics and type safety.

    Attributes:
        status: Status code object
        data: Return data (result on success, e.g., ModelConfig object)
        details: Details dictionary (parameters for message formatting)
    """
    status: StatusCode
    data: Optional[Any] = None
    details: Optional[Dict[str, Any]] = None

    @property
    def success(self) -> bool:
        """Whether the operation succeeded"""
        return self.status.is_success

    @property
    def failed(self) -> bool:
        """Whether the operation failed (error or critical error)"""
        return self.status.is_error

    @property
    def has_warning(self) -> bool:
        """Whether there is a warning"""
        return self.status.is_warning

    @property
    def has_info(self) -> bool:
        """Whether this is an info status"""
        return self.status.is_info

    def get_message(self, **kwargs) -> str:
        """
        Get formatted status message

        Args:
            **kwargs: Additional format parameters (will override same-named parameters in details)

        Returns:
            Formatted message string
        """
        if self.details and "_formatted_message" in self.details:
            return self.details["_formatted_message"]

        try:
            format_args = {**(self.details or {}), **kwargs}
            return self.status.message_template.format(**format_args)
        except KeyError:
            return self.status.message_template

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary format (for API responses, logging, etc.)

        Returns:
            Dictionary containing status code, message, and data
        """
        result = {
            "code": self.status.code,
            "name": self.status.name,
            "level": self.status.level.value,
            "message": self.get_message(),
        }
        if self.data is not None:
            result["data"] = self.data
        return result