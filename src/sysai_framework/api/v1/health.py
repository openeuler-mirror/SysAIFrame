"""
Copyright (C) 2025 CTyunOS. All Rights Reserved.
File: health.py
Desc: Health status REST API endpoints
Date: 2026-01-16
Author: Liu Mingran
"""

from fastapi import APIRouter, HTTPException, status
from typing import Dict, Any, Optional
from sysai_framework.router.model_router import get_router

router = APIRouter(prefix="/v1/health", tags=["health"])


@router.get("/models")
async def get_all_models_health() -> Dict[str, Any]:
    """
    Get health status for all models
    
    Returns:
        Detailed health status for each model
    """
    try:
        model_router = get_router()
        stats = model_router.get_health_statistics()
        
        return {
            "total_models": stats.get("total_models", 0),
            "healthy_models": stats.get("healthy_models", 0),
            "unhealthy_models": stats.get("unhealthy_models", 0),
            "models": stats.get("models", [])
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get models health: {str(e)}"
        )
