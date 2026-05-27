"""
Copyright (C) 2025 CTyunOS. All Rights Reserved.
File: main.py
Desc: Main application for SysAIFrame AI Gateway
     Unified AI service gateway entry point
Date: 2025-10-22
Author: Liu Mingran
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sysai_framework.api.v1 import chat
from sysai_framework.api.v1 import health
from sysai_framework.config import config
import uvicorn
import logging
import os
import atexit

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Reduce third-party library log verbosity
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

# Create FastAPI application
app = FastAPI(
    title="SysAIFrame AI Gateway",
    description="Unified AI Service Gateway - Chat Completion API Compatible",
    version="0.1.0",
    docs_url=None,
    redoc_url=None
)
