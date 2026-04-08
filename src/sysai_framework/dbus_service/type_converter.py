"""
Copyright (C) 2025 CTyunOS. All Rights Reserved.
File: type_converter.py
Desc: Type conversion utilities between Python and D-Bus types
Date: 2025-11-18
Author: Liu Mingran
"""

import logging
from typing import Any, Dict, List, Union

logger = logging.getLogger(__name__)

# Platform detection for conditional imports
try:
    import dbus
    DBUS_AVAILABLE = True
except ImportError:
    DBUS_AVAILABLE = False
    logger.warning("dbus-python not available - D-Bus service will not work on this platform")


def python_to_dbus(value: Any) -> Any:
    """
    Convert Python value to D-Bus compatible type.

    Args:
        value: Python value (dict, list, str, int, float, bool, None)

    Returns:
        D-Bus compatible value
    """
    if not DBUS_AVAILABLE:
        return value

    if value is None:
        # D-Bus doesn't have null, use empty string
        return dbus.String('')
    elif isinstance(value, bool):
        return dbus.Boolean(value)
    elif isinstance(value, int):
        return dbus.Int64(value)
    elif isinstance(value, float):
        return dbus.Double(value)
    elif isinstance(value, str):
        return dbus.String(value)
    elif isinstance(value, list):
        if not value:
            return dbus.Array([], signature='v')
        # Convert list elements
        converted = [python_to_dbus(item) for item in value]
        return dbus.Array(converted, signature='v')
    elif isinstance(value, dict):
        # Convert dict to D-Bus dictionary with string keys and variant values
        converted = {}
        for k, v in value.items():
            converted[str(k)] = python_to_dbus(v)
        return dbus.Dictionary(converted, signature='sv')
    else:
        # Fallback: convert to string
        logger.warning(f"Unknown type {type(value)}, converting to string")
        return dbus.String(str(value))


def dbus_to_python(value: Any) -> Any:
    """
    Convert D-Bus value to Python type.

    Args:
        value: D-Bus value

    Returns:
        Python value
    """
    if not DBUS_AVAILABLE:
        return value

    if isinstance(value, dbus.Dictionary):
        return {dbus_to_python(k): dbus_to_python(v) for k, v in value.items()}
    elif isinstance(value, dbus.Array):
        return [dbus_to_python(item) for item in value]
    elif isinstance(value, dbus.Boolean):
        return bool(value)
    elif isinstance(value, (dbus.Int16, dbus.Int32, dbus.Int64,
                           dbus.UInt16, dbus.UInt32, dbus.UInt64)):
        return int(value)
    elif isinstance(value, dbus.Double):
        return float(value)
    elif isinstance(value, (dbus.String, dbus.ObjectPath, dbus.Signature)):
        s = str(value)
        # Empty string represents null in our convention
        return None if s == '' else s
    elif isinstance(value, dbus.Byte):
        return int(value)
    else:
        # For basic Python types passed through
        return value


def request_to_python(dbus_request: Dict) -> Dict:
    """
    Convert D-Bus request dict to Python dict for internal processing.

    Args:
        dbus_request: D-Bus request dictionary

    Returns:
        Python dictionary
    """
    if not DBUS_AVAILABLE:
        return dbus_request

    try:
        python_req = dbus_to_python(dbus_request)

        # Special handling for messages field
        if 'messages' in python_req and isinstance(python_req['messages'], list):
            # Ensure each message is a proper dict
            messages = []
            for msg in python_req['messages']:
                if isinstance(msg, dict):
                    messages.append(msg)
                else:
                    logger.warning(f"Invalid message format: {msg}")
            python_req['messages'] = messages

        return python_req
    except Exception as e:
        logger.error(f"Error converting request: {e}")
        raise


def response_to_dbus(python_response: Dict) -> Any:
    """
    Convert Python response dict to D-Bus format.

    Args:
        python_response: Python response dictionary

    Returns:
        D-Bus dictionary
    """
    if not DBUS_AVAILABLE:
        return python_response

    try:
        return python_to_dbus(python_response)
    except Exception as e:
        logger.error(f"Error converting response: {e}")
        raise


def models_to_dbus(models: List[str]) -> Any:
    """
    Convert Python model list to D-Bus string array.

    Args:
        models: List of model names

    Returns:
        D-Bus array of strings
    """
    if not DBUS_AVAILABLE:
        return models

    try:
        return dbus.Array([dbus.String(m) for m in models], signature='s')
    except Exception as e:
        logger.error(f"Error converting models: {e}")
        raise


