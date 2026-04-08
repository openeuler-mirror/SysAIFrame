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
