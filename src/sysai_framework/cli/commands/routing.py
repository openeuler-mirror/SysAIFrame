"""
Copyright (C) 2025 CTyunOS. All Rights Reserved.
File: cli/commands/routing.py
Desc: CLI commands for routing configuration
Date: 2025-11-27
Author: Liu Mingran
"""

import click
import sys
import logging
from typing import Optional

from ..utils.output import Output
from ..utils.mode_switch import auto_execute
from ..constants import DEFAULT_CONFIG_PATH

logger = logging.getLogger(__name__)


@click.group(name='routing')
def routing():
    """Routing configuration management commands"""
    pass
