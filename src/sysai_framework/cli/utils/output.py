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
    
    @staticmethod
    def json_output(data: Any) -> None:
        """Print data as formatted JSON"""
        click.echo(json.dumps(data, indent=2, ensure_ascii=False))
    
    @staticmethod
    def print_json(data: Any) -> None:
        """Print data as formatted JSON (alias for json_output)"""
        Output.json_output(data)
    
    @staticmethod
    def section(title: str) -> None:
        """Print section header"""
        click.echo("")
        click.echo(click.style(title, fg='cyan', bold=True))
    
    @staticmethod
    def model_info(model_data: Dict[str, Any]) -> None:
        """Print model configuration info"""
        click.echo(f"Model: {model_data.get('name', 'N/A')}")
        click.echo(f"  Instance ID: {model_data.get('instance_id', 'auto-generated')}")
        click.echo(f"  Provider: {model_data.get('provider', 'openai_like')}")
        click.echo(f"  API: {model_data.get('api_base', 'N/A')}")
        click.echo(f"  Priority: {model_data.get('priority', 1)}")
        click.echo(f"  Capabilities: {', '.join(model_data.get('capabilities', ['general']))}")
        timeout_display = model_data.get('timeout')
        if timeout_display is None or timeout_display == 'inherit (routing)':
            timeout_str = 'inherit (routing)'
        else:
            timeout_str = f"{timeout_display}s"
        click.echo(f"  Timeout: {timeout_str}")
        stream_timeout_display = model_data.get('stream_timeout')
        if stream_timeout_display is None or stream_timeout_display == 'inherit (timeout)':
            stream_timeout_str = 'inherit (timeout)'
        else:
            stream_timeout_str = f"{stream_timeout_display}s"
        click.echo(f"  Stream Timeout: {stream_timeout_str}")
        click.echo(f"  Max Retries: {model_data.get('max_retries', 3)}")
        click.echo(f"  Streaming: {model_data.get('supports_streaming', True)}")
    
    @staticmethod
    def validation_errors(errors: List[str]) -> None:
        """Print validation errors"""
        Output.error("Validation failed:")
        for error in errors:
            click.echo(f"  • {error}", err=True)

    @staticmethod
    def sanitize_sensitive_data(data: Any) -> Any:
        """
        Recursively sanitize sensitive information in data structures.
        
        Replaces sensitive fields (api_key, api-key, API_KEY, etc.) with '***'.
        
        Args:
            data: Data structure (dict, list, or primitive) to sanitize
            
        Returns:
            Sanitized data structure with sensitive fields replaced
        """
        # List of sensitive field names (case-insensitive matching)
        SENSITIVE_FIELDS = {'api_key', 'api-key', 'api_key', 'API_KEY', 'secret', 'password', 'token'}
        
        if isinstance(data, dict):
            sanitized = {}
            for key, value in data.items():
                # Check if key is a sensitive field (case-insensitive)
                key_lower = key.lower().replace('-', '_').replace(' ', '_')
                if key_lower in SENSITIVE_FIELDS or any(sensitive in key_lower for sensitive in ['api_key', 'secret', 'password', 'token']):
                    # Replace sensitive value with '***' if it exists and is not empty
                    sanitized[key] = '***' if value else value
                else:
                    # Recursively sanitize nested structures
                    sanitized[key] = Output.sanitize_sensitive_data(value)
            return sanitized
        elif isinstance(data, list):
            return [Output.sanitize_sensitive_data(item) for item in data]
        else:
            # Primitive types (str, int, bool, None, etc.) - return as is
            return data


