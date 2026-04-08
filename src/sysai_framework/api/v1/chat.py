"""
Copyright (C) 2025 CTyunOS. All Rights Reserved.
File: chat.py
Desc: Chat completion API endpoints for SysAIFrame
     Implements Chat Completion API compatible interface
Date: 2025-10-22
Author: Liu Mingran
"""

from fastapi import APIRouter, Header, HTTPException, status, Request
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Union
import logging
import time
import uuid

from sysai_framework.router.model_router import get_router
from sysai_framework.core import (
    handle_exception_with_logging,
    get_hook_manager
)
from sysai_framework.core.chat_processor import ChatCompletionProcessor

logger = logging.getLogger(__name__)

router = APIRouter()
