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


@service.command('status')
@click.option('--json', 'output_json', is_flag=True, help='Output in JSON format')
def status_cmd(output_json: bool):
    """
    Query service operational status
    
    Shows:
      - Service state (INITIALIZING, READY, DEGRADED, ERROR)
      - Model count and health status
      - Configuration load status
    
    Examples:
        ai-config service status
        ai-config service status --json
    """
    try:
        client = get_dbus_client()
        
        # Check if service is running by trying to get status
        if not client.is_service_running():
            if output_json:
                status_info = {
                    "state": "NOT_RUNNING",
                    "message": "Service is not running",
                    "model_count": 0,
                    "healthy_model_count": 0,
                    "config_status": {
                        "last_load_success": False,
                        "last_load_message": "Service not running"
                    }
                }
                click.echo(json.dumps(status_info, indent=2, ensure_ascii=False))
            else:
                Output.warning("Service is not running")
                Output.info("Start the service with: sudo systemctl start sysaiframe")
            sys.exit(Output.EXIT_SERVICE_NOT_RUNNING)
        
        # Get service status via D-Bus
        status_info = client.get_service_status()
        
        if output_json:
            click.echo(json.dumps(status_info, indent=2, ensure_ascii=False))
        else:
            # Format status for human-readable output
            state = status_info.get('state', 'UNKNOWN')
            message = status_info.get('message', 'No message')
            model_count = status_info.get('model_count', 0)
            healthy_count = status_info.get('healthy_model_count', 0)
            config_status = status_info.get('config_status', {})
            
            # Choose color based on state
            if state == "READY":
                state_color = "green"
            elif state == "DEGRADED":
                state_color = "yellow"
            elif state == "ERROR":
                state_color = "red"
            elif state == "INITIALIZING":
                state_color = "blue"
            else:
                state_color = "white"
            
            Output.info(f"Service State: {click.style(state, fg=state_color)}")
            Output.info(f"   Message: {message}")
            Output.info(f"   Models: {healthy_count}/{model_count} healthy")
            
            if config_status:
                config_success = config_status.get('last_load_success', False)
                config_message = config_status.get('last_load_message', 'Unknown')
                config_color = "green" if config_success else "red"
                Output.info(f"   Config: {click.style(config_message, fg=config_color)}")
        
        # Return appropriate exit code based on state
        if status_info.get('state') == "READY":
            sys.exit(0)
        elif status_info.get('state') == "DEGRADED":
            sys.exit(1)  # Non-zero but not critical
        else:
            sys.exit(1)
            
    except ServiceNotRunningError:
        if output_json:
            status_info = {
                "state": "NOT_RUNNING",
                "message": "Service is not running",
                "model_count": 0,
                "healthy_model_count": 0,
                "config_status": {
                    "last_load_success": False,
                    "last_load_message": "Service not running"
                }
            }
            click.echo(json.dumps(status_info, indent=2, ensure_ascii=False))
        else:
            Output.warning("Service is not running")
            Output.info("Start the service with: sudo systemctl start sysaiframe")
        sys.exit(Output.EXIT_SERVICE_NOT_RUNNING)
    except DBusClientError as e:
        Output.error(f"Failed to query service status: {e}")
        logger.error(f"D-Bus error: {e}", exc_info=True)
        sys.exit(Output.EXIT_DBUS_ERROR)
    except Exception as e:
        Output.error(f"Unexpected error: {e}")
        logger.error(f"Unexpected error: {e}", exc_info=True)
        sys.exit(1)


@service.command('reload')
@click.option('--source', 'source_file', 
              help='Source configuration file path to copy and reload (optional)')
def reload_cmd(source_file: Optional[str]):
    """
    Reload configuration
    
    Reloads the service configuration. If --source is specified, copies the source
    file to the service's current configuration path before reloading.
    Changes take effect immediately without restarting the service.
    
    Examples:
        ai-config service reload
        ai-config service reload --source /path/to/config.yaml
    """
    import os
    import shutil
    
    try:
        client = get_dbus_client()
        
        # Check if service is running
        if not client.is_service_running():
            Output.error("Service is not running")
            Output.info("Start the service with: sudo systemctl start sysaiframe")
            sys.exit(Output.EXIT_SERVICE_NOT_RUNNING)
        
        # If source file is specified, copy it to service config path
        if source_file:
            # Check if source file exists
            if not os.path.exists(source_file):
                Output.error(f"Source configuration file not found: {source_file}")
                sys.exit(Output.EXIT_CONFIG_NOT_FOUND)
            
            # Get service's current configuration path
            try:
                service_config_path = client.get_service_config_path()
                if not service_config_path or not service_config_path.strip():
                    Output.error("Failed to get service configuration path")
                    sys.exit(Output.EXIT_DBUS_ERROR)
            except Exception as e:
                Output.error(f"Failed to get service configuration path: {e}")
                sys.exit(Output.EXIT_DBUS_ERROR)
            
            # Normalize paths
            source_path = os.path.realpath(os.path.abspath(source_file))
            target_path = os.path.realpath(os.path.abspath(service_config_path))
            
            # If source and target are the same, skip copy
            if source_path == target_path:
                Output.info("Source file is the same as service config file, skipping copy")
            else:
                # Ensure target directory exists
                target_dir = os.path.dirname(target_path)
                if not os.path.exists(target_dir):
                    os.makedirs(target_dir, mode=0o755, exist_ok=True)
                
                # Atomic write: write to temporary file first, then rename
                temp_path = f"{target_path}.tmp"
                try:
                    # Copy source file to temporary file
                    shutil.copy2(source_path, temp_path)
                    
                    # Atomically replace target file
                    os.replace(temp_path, target_path)
                    
                    # Ensure directory entry is synced
                    try:
                        dir_fd = os.open(target_dir, os.O_RDONLY)
                        try:
                            os.fsync(dir_fd)
                        finally:
                            os.close(dir_fd)
                    except (OSError, IOError):
                        # If directory sync fails, it's not critical
                        pass
                    
                    Output.info(f"Configuration copied from {source_path} to {target_path}")
                except Exception as e:
                    # Clean up temporary file on error
                    try:
                        if os.path.exists(temp_path):
                            os.unlink(temp_path)
                    except OSError:
                        pass
                    Output.error(f"Failed to copy configuration file: {e}")
                    sys.exit(Output.EXIT_WRITE_FAILED)
        
        # Reload configuration via D-Bus
        Output.info("Reloading configuration...")
        result = client.reload_config()
        
        if result.success:
            Output.success("Configuration reloaded successfully")
            sys.exit(0)
        else:
            Output.error(f"Failed to reload configuration: {result.get_message()}")
            sys.exit(1)
            
    except ServiceNotRunningError:
        Output.error("Service is not running")
        Output.info("Start the service with: sudo systemctl start sysaiframe")
        sys.exit(Output.EXIT_SERVICE_NOT_RUNNING)
    except DBusClientError as e:
        Output.error(f"Failed to reload configuration: {e}")
        logger.error(f"D-Bus error: {e}", exc_info=True)
        sys.exit(Output.EXIT_DBUS_ERROR)
    except Exception as e:
        Output.error(f"Unexpected error: {e}")
        logger.error(f"Unexpected error: {e}", exc_info=True)
        sys.exit(1)

