"""
Copyright (C) 2025 CTyunOS. All Rights Reserved.
File: __init__.py
Desc: Core module initialization for SysAIFrame
     Enhanced request processing, error handling and utilities
Date: 2025-10-22
Author: Liu Mingran
"""

from sysai_framework.core.exceptions import (
    CompatibleException,
    ModelNotFoundError,
    InvalidRequestError,
    AuthenticationError,
    RateLimitError,
    ServiceUnavailableError,
    TimeoutError,
    handle_exception_with_logging
)
