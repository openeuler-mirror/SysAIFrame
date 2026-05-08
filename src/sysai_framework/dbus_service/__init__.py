"""
Copyright (C) 2025 CTyunOS. All Rights Reserved.
File: __init__.py
Desc: D-Bus service module for SysAIFrame Gateway
      Provides system-level D-Bus interface for AI services
Date: 2025-11-18
Author: Liu Mingran
"""

from .service import (
    DBusAIGatewayService,
    set_service_instance,
    get_service_instance,
    get_admin_service
)

__all__ = [
    'DBusAIGatewayService',
    'set_service_instance',
    'get_service_instance',
    'get_admin_service'
]
