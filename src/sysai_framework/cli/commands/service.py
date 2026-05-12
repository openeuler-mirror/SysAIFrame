"""
Copyright (C) 2025 CTyunOS. All Rights Reserved.
File: cli/commands/service.py
Desc: CLI commands for service management
Date: 2025-11-27
Author: Liu Mingran
"""

import click
import sys
import json
import logging
from typing import Optional

from ..utils.output import Output
from ..utils.dbus_client import get_dbus_client, ServiceNotRunningError, DBusClientError

logger = logging.getLogger(__name__)


@click.group(name='service')
def service():
    """Service management commands"""
    pass
