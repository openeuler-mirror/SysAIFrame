"""
Copyright (C) 2025 CTyunOS. All Rights Reserved.
File: strategies/least_busy.py
Desc: Least-busy load balance strategy - selects model with fewest active requests
Date: 2025-01-26
Author: Liu Mingran
"""

import threading
from typing import List, Optional, Dict

from sysai_framework.config.model_config import ModelConfig
from sysai_framework.router.routing_strategy import BaseRoutingStrategy

import logging

logger = logging.getLogger(__name__)


class LeastBusyStrategy(BaseRoutingStrategy):
    """Least-busy load balance strategy - selects model with fewest active requests"""
    
    def __init__(self, config_manager=None):
        super().__init__(config_manager)
        # Track active request count per model instance_id
        self._request_counts: Dict[str, int] = {}
        self._lock = threading.Lock()
    
    def select_deployment(
        self, 
        healthy_models: List[ModelConfig]
    ) -> Optional[ModelConfig]:
        """
        Select model with fewest active requests
        
        Args:
            healthy_models: List of healthy ModelConfig instances
            
        Returns:
            Selected ModelConfig or None if no models available
        """
        if not healthy_models:
            return None
        
        with self._lock:
            # Get request counts for all healthy models
            counts = [
                (model, self._request_counts.get(model.instance_id, 0))
                for model in healthy_models
            ]
            
            # Sort by request count (ascending)
            counts.sort(key=lambda x: x[1])
            
            # Select model with minimum count
            selected = counts[0][0]
            
            logger.debug(
                f"Least-busy selected: {selected.name} "
                f"(instance_id={selected.instance_id}, active_requests={counts[0][1]})"
            )
            return selected
    
    def log_pre_call(self, model_config: ModelConfig) -> None:
        """Increment request count before call"""
        with self._lock:
            current = self._request_counts.get(model_config.instance_id, 0)
            self._request_counts[model_config.instance_id] = current + 1
    
    def log_success(
        self, 
        model_config: ModelConfig, 
        response_time: float,
        tokens_used: int = 0
    ) -> None:
        """Decrement request count on success"""
        with self._lock:
            current = self._request_counts.get(model_config.instance_id, 0)
            if current > 0:
                self._request_counts[model_config.instance_id] = current - 1
    
    def log_failure(self, model_config: ModelConfig) -> None:
        """Decrement request count on failure"""
        with self._lock:
            current = self._request_counts.get(model_config.instance_id, 0)
            if current > 0:
                self._request_counts[model_config.instance_id] = current - 1
