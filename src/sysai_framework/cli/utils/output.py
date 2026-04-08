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

    @staticmethod
    def success(message: str) -> None:
        """Print success message in green"""
        click.echo(click.style(message, fg='green'))

    @staticmethod
    def error(message: str) -> None:
        """Print error message in red"""
        click.echo(click.style(message, fg='red'), err=True)

    @staticmethod
    def warning(message: str) -> None:
        """Print warning message in yellow"""
        click.echo(click.style(message, fg='yellow'), err=True)

    @staticmethod
    def info(message: str) -> None:
        """Print info message"""
        click.echo(message)

    @staticmethod
    def print_result(result: 'OperationResult') -> None:
        """
        Print OperationResult with appropriate styling

        Args:
            result: OperationResult object from status code system
        """
        from sysai_framework.core.status_codes import StatusLevel

        message = result.get_message()

        if result.status.level == StatusLevel.SUCCESS:
            Output.success(message)
        elif result.status.level == StatusLevel.INFO:
            Output.info(message)
        elif result.status.level == StatusLevel.WARNING:
            Output.warning(message)
        elif result.status.level in (StatusLevel.ERROR, StatusLevel.CRITICAL):
            Output.error(message)
        else:
            # Default
            click.echo(message)

    @staticmethod
    def table(headers: List[str], rows: List[List[str]]) -> None:
        """Print data as a formatted table"""
        if not rows:
            click.echo("No data to display.")
            return

        # Calculate column widths
        col_widths = [len(h) for h in headers]
        for row in rows:
            for i, cell in enumerate(row):
                if i < len(col_widths):
                    col_widths[i] = max(col_widths[i], len(str(cell)))

        # Print header
        header_line = " | ".join(
            h.ljust(col_widths[i]) for i, h in enumerate(headers)
        )
        click.echo(header_line)
        click.echo("-" * len(header_line))

        # Print rows
        for row in rows:
            row_line = " | ".join(
                str(cell).ljust(col_widths[i]) for i, cell in enumerate(row)
            )
            click.echo(row_line)
