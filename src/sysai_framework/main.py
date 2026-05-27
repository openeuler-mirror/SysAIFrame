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

# CORS middleware - strict local-only by default, remote access only in test mode
@app.middleware("http")
async def cors_middleware(request: Request, call_next):
    """CORS policy - local only by default, remote access requires TEST_MODE=true
    
    Default: Only allow local origins (localhost, 127.0.0.1, etc.)
    Test Mode: Allow configured remote origins with TEST_MODE=true and CORS_ALLOWED_HOSTS
    """
    
    origin = request.headers.get("origin")
    
    # Handle preflight requests
    if request.method == "OPTIONS":
        if origin and config.is_origin_allowed(origin):
            # Allow preflight requests from allowed origins
            from fastapi import Response
            response = Response(status_code=200)
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
            response.headers["Access-Control-Allow-Methods"] = "GET,POST,PUT,DELETE,OPTIONS"
            response.headers["Access-Control-Allow-Headers"] = "Accept,Accept-Language,Content-Language,Content-Type,Authorization,X-Requested-With,Origin,Access-Control-Request-Method,Access-Control-Request-Headers"
            response.headers["Access-Control-Max-Age"] = "86400"
            return response
        else:
            # Reject non-allowed preflight requests
            from fastapi import HTTPException
            logger.warning(f"CORS blocked preflight request from: {origin}")
            raise HTTPException(status_code=403, detail="CORS: Origin not allowed")
    
    # Handle actual requests
    if origin and not config.is_origin_allowed(origin):
        # Reject non-allowed requests
        logger.warning(f"CORS blocked request from: {origin}")
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="CORS: Origin not allowed")
    
    response = await call_next(request)
    
    # Add CORS headers for allowed requests
    if origin and config.is_origin_allowed(origin):
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Access-Control-Expose-Headers"] = "*"
        
        # Log remote connections for monitoring
        if not config._is_local_origin(origin):
            logger.info(f"Remote connection from: {origin}")
    
    return response
