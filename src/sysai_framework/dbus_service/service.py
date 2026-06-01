"""
Copyright (C) 2025 CTyunOS. All Rights Reserved.
File: service.py
Desc: D-Bus service implementation for SysAIFrame Gateway
Date: 2025-11-18
Author: Liu Mingran
"""

import os
import logging
import threading
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# Platform detection
try:
    import dbus
    import dbus.service
    from dbus.mainloop.glib import DBusGMainLoop
    from gi.repository import GLib
    DBUS_AVAILABLE = True
except ImportError:
    DBUS_AVAILABLE = False
    logger.warning("D-Bus dependencies not available - service will not start")


# Read interface XML
INTERFACE_XML_PATH = os.path.join(os.path.dirname(__file__), 'interface.xml')


class DBusAIGatewayService:
    """
    D-Bus service for SysAIFrame Gateway.
    Provides system-level interface for AI chat completions and admin operations.
    """
    
    BUS_NAME = 'org.ctyunos.AIGateway.Chat'
    OBJECT_PATH = '/org/ctyunos/AIGateway/Chat'
    ADMIN_OBJECT_PATH = '/org/ctyunos/AIGateway/Admin'
    INTERFACE_NAME = 'org.ctyunos.AIGateway.Chat'
    ADMIN_INTERFACE_NAME = 'org.ctyunos.AIGateway.Admin'
    
    def __init__(self, gateway_app=None, use_system_bus: bool = True):
        """
        Initialize D-Bus service.
        
        Args:
            gateway_app: FastAPI application instance (for accessing routes)
            use_system_bus: Use system bus (True) or session bus (False)
        """
        self.gateway_app = gateway_app
        self.use_system_bus = use_system_bus
        self.bus = None
        self.bus_name = None
        self.service_object = None
        self.admin_service_object = None
        self.mainloop = None
        self.thread = None
        self.running = False
        
        if not DBUS_AVAILABLE:
            logger.error("Cannot initialize D-Bus service: dependencies not available")
            return
        
        logger.info(f"D-Bus service initialized for {self.BUS_NAME}")
    
    def start(self):
        """Start D-Bus service in a separate thread."""
        if not DBUS_AVAILABLE:
            logger.warning("D-Bus not available, skipping service start")
            return
        
        if self.running:
            logger.warning("D-Bus service already running")
            return
        
        self.thread = threading.Thread(target=self._run_service, daemon=True)
        self.thread.start()
        logger.info("D-Bus service thread started")
    
    def _run_service(self):
        """Run D-Bus service in its own thread."""
        try:
            # Initialize GLib main loop
            DBusGMainLoop(set_as_default=True)
            
            # Connect to bus
            if self.use_system_bus:
                try:
                    self.bus = dbus.SystemBus()
                    logger.info("Connected to system D-Bus")
                except Exception as e:
                    logger.warning(f"Failed to connect to system bus: {e}. Falling back to session bus.")
                    self.bus = dbus.SessionBus()
                    logger.info("Connected to session D-Bus")
            else:
                self.bus = dbus.SessionBus()
                logger.info("Connected to session D-Bus")
            
            # Request bus name
            self.bus_name = dbus.service.BusName(self.BUS_NAME, bus=self.bus)
            
            # Create chat service object
            from .chat_methods import ChatServiceObject
            self.service_object = ChatServiceObject(
                self.bus_name,
                self.OBJECT_PATH,
                gateway_app=self.gateway_app
            )
            
            # Create admin service object
            from .admin_methods import AdminServiceObject
            self.admin_service_object = AdminServiceObject(
                self.bus_name,
                self.ADMIN_OBJECT_PATH
            )
            
            # Create and run main loop
            self.mainloop = GLib.MainLoop()
            self.running = True
            
            logger.info(f"D-Bus service '{self.BUS_NAME}' ready at '{self.OBJECT_PATH}'")
            logger.info(f"D-Bus admin service ready at '{self.ADMIN_OBJECT_PATH}'")
            self.mainloop.run()
            
        except Exception as e:
            logger.error(f"D-Bus service error: {e}", exc_info=True)
            self.running = False
    
    def stop(self):
        """Stop D-Bus service."""
        if not self.running:
            return
        
        logger.info("Stopping D-Bus service...")
        self.running = False
        
        if self.mainloop:
            self.mainloop.quit()
        
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=5)
            if self.thread.is_alive():
                logger.warning("D-Bus service thread did not stop within timeout")
        
        logger.info("D-Bus service stopped")
    
    def is_running(self) -> bool:
        """Check if service is running."""
        return self.running


# Global service instance management
_service_instance: Optional[DBusAIGatewayService] = None


def set_service_instance(service: DBusAIGatewayService) -> None:
    """
    Set the global D-Bus service instance.
    
    Args:
        service: DBusAIGatewayService instance
    """
    global _service_instance
    _service_instance = service


def get_service_instance() -> Optional[DBusAIGatewayService]:
    """
    Get the global D-Bus service instance.
    
    Returns:
        DBusAIGatewayService instance or None if not set
    """
    return _service_instance


def get_admin_service():
    """
    Get the admin service object for emitting signals.
    
    Returns:
        Admin service object or None if not available
    """
    service = get_service_instance()
    if service and service.admin_service_object:
        return service.admin_service_object
    return None
