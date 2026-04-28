"""
Copyright (C) 2025 CTyunOS. All Rights Reserved.
File: strategies/weighted.py
Desc: Weighted random load balance strategy
Date: 2025-01-26
Author: Liu Mingran
"""

import random
from typing import List, Optional

from sysai_framework.config.model_config import ModelConfig
from sysai_framework.router.routing_strategy import BaseRoutingStrategy

import logging

logger = logging.getLogger(__name__)


class WeightedStrategy(BaseRoutingStrategy):
    """Weighted random load balance strategy - selects based on weight"""

    def select_deployment(
        self,
        healthy_models: List[ModelConfig]
    ) -> Optional[ModelConfig]:
        """
        Select model based on weight (weighted random)

        Args:
            healthy_models: List of healthy ModelConfig instances

        Returns:
            Selected ModelConfig or None if no models available
        """
        if not healthy_models:
            return None

        weights = [model.weight for model in healthy_models]
        total_weight = sum(weights)

        if total_weight == 0:
            selected = random.choice(healthy_models)
        else:
            selected = random.choices(healthy_models, weights=weights, k=1)[0]

        logger.debug(
            f"Weighted selected: {selected.name} "
            f"(instance_id={selected.instance_id}, weight={selected.weight})"
        )
        return selected
