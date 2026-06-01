"""
Copyright (C) 2025 CTyunOS. All Rights Reserved.
File: service_status.py
Desc: Service status management for SysAIFrame
     Tracks service state and model availability
Date: 2025-11-27
Author: Liu Mingran
"""

from enum import Enum
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class ServiceState(Enum):
    """Service state enumeration"""
    INITIALIZING = "initializing"  # Service is initializing
    READY = "ready"                # Running normally with available models
    DEGRADED = "degraded"          # Running in degraded state (no available models)
    ERROR = "error"                # Error state


class ServiceStatus:
    """
    Service status manager
    
    Tracks and reports the overall service status including:
    - Service state (initializing/ready/degraded/error)
    - Number of configured models
    - Number of healthy models
    - Error messages if any
    """
    
    def __init__(self):
        self.state: ServiceState = ServiceState.INITIALIZING
        self.total_models: int = 0
        self.healthy_models: int = 0
        self.error_message: Optional[str] = None
        self._last_update: Optional[float] = None
    
    def update_from_config(self, config_manager) -> None:
        """
        Update status from configuration manager
        
        Args:
            config_manager: ModelConfigManager instance
        """
        from time import time
        
        try:
            # Get all models
            all_models = list(config_manager.models.values())
            self.total_models = len(all_models)
            self.healthy_models = len([m for m in all_models if m.is_healthy])
            
            # Determine service state
            if self.healthy_models > 0:
                self.state = ServiceState.READY
                self.error_message = None
                logger.debug(
                    f"Service state: READY ({self.healthy_models}/{self.total_models} models healthy)"
                )
            elif self.total_models > 0:
                self.state = ServiceState.DEGRADED
                self.error_message = f"No healthy models available ({self.total_models} configured but unhealthy)"
                logger.warning(self.error_message)
            else:
                self.state = ServiceState.DEGRADED
                self.error_message = "No models configured. Use 'ai-config model add' to add models."
                logger.warning(self.error_message)
            
            self._last_update = time()
            
        except Exception as e:
            self.state = ServiceState.ERROR
            self.error_message = f"Failed to update service status: {str(e)}"
            logger.error(self.error_message, exc_info=True)
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert status to dictionary format
        
        Returns:
            Dictionary containing status information
        """
        return {
            "state": self.state.value,
            "total_models": self.total_models,
            "healthy_models": self.healthy_models,
            "error_message": self.error_message,
            "last_update": self._last_update
        }
    
    def is_ready(self) -> bool:
        """Check if service is ready (has healthy models)"""
        return self.state == ServiceState.READY
    
    def is_degraded(self) -> bool:
        """Check if service is in degraded state"""
        return self.state == ServiceState.DEGRADED


# Global status instance
_service_status: Optional[ServiceStatus] = None


def get_service_status() -> ServiceStatus:
    """Get service status singleton instance"""
    global _service_status
    if _service_status is None:
        _service_status = ServiceStatus()
    return _service_status


def update_service_status(config_manager) -> None:
    """
    Update service status from config manager
    
    Args:
        config_manager: ModelConfigManager instance
    """
    status = get_service_status()
    status.update_from_config(config_manager)

