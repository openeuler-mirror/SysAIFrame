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
