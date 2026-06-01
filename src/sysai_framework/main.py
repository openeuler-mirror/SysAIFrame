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
from sysai_framework.config.cors_config import Config
from sysai_framework.config.model_config import get_config_manager
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

# Global config instance - initialized by main() after ModelConfigManager
config = None

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

# Register API routes
app.include_router(chat.router, prefix="/v1", tags=["Chat Completions"])
app.include_router(health.router, tags=["Health"])


@app.get("/")
async def root():
    """Root endpoint - Service information"""
    return {
        "service": "SysAIFrame AI Gateway",
        "version": "0.1.0",
        "status": "running"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "sysaiframe-gateway"
    }


@app.on_event("shutdown")
async def shutdown_event():
    """Handle shutdown event - stop background tasks"""
    logger.info("Shutting down...")
    
    # Stop health checker background tasks
    try:
        from sysai_framework.router.model_router import get_router
        router = get_router()
        if hasattr(router, 'health_checker') and router.health_checker:
            logger.info("Stopping health checker background tasks...")
            router.health_checker.stop_background_checks()
    except Exception as e:
        logger.warning(f"Error stopping health checker: {e}")
    
    # D-Bus service will be stopped in finally block or atexit handler
    logger.info("Shutdown event completed")


def main():
    """Main entry point"""
    # Initialize config manager via singleton (respects SYSAIFRAME_CONFIG_PATH env var)
    config_manager = get_config_manager()
    gateway_config = config_manager.get_gateway_config()

    global config
    config = Config(gateway_config=gateway_config)

    # Configure CORS middleware with dynamic configuration (after config is initialized)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.get_cors_origins(),
        allow_credentials=config.get_cors_credentials(),
        allow_methods=config.get_cors_methods(),
        allow_headers=config.get_cors_headers(),
        expose_headers=["*"],
    )

    logger.info("Starting SysAIFrame AI Gateway...")
    logger.info(f"CORS Policy: {'TEST MODE - Remote access enabled' if config.test_mode else 'PRODUCTION - Local access only'}")
    if config.test_mode:
        logger.warning("TEST_MODE is enabled - Remote access is allowed")
        if config.allowed_remote_hosts:
            logger.info(f"Allowed remote hosts: {', '.join(config.allowed_remote_hosts)}")
        else:
            logger.info("Allowed remote hosts: ANY (CORS_ALLOWED_HOSTS not set)")

    logger.info(f"Gateway: remote_access={config.remote_access}, binding to {config.gateway_host}:{config.gateway_port}")
    
    # Initialize D-Bus service if enabled and available
    dbus_service = None
    enable_dbus = os.getenv('ENABLE_DBUS', 'true').lower() == 'true'
    
    if enable_dbus:
        try:
            from sysai_framework.dbus_service import DBusAIGatewayService
            dbus_service = DBusAIGatewayService(gateway_app=app, use_system_bus=True)
            dbus_service.start()
            logger.info("D-Bus service started")
            
            # Register cleanup
            def cleanup_dbus():
                if dbus_service:
                    logger.info("Shutting down D-Bus service...")
                    dbus_service.stop()
            
            atexit.register(cleanup_dbus)
        except Exception as e:
            logger.warning(f"D-Bus service not started: {e}")
            logger.info("Gateway will run without D-Bus support")
    else:
        logger.info("D-Bus service disabled (ENABLE_DBUS=false)")
    
    try:
        # Use host from config (defaults to 0.0.0.0 for external access)
        host = config.gateway_host
        port = config.gateway_port
        logger.info(f"Starting server on {host}:{port}")
        uvicorn.run(
            app,
            host=host,
            port=port,
            log_level="warning",  # Reduce uvicorn access logs (use WARNING to only show errors)
            access_log=False,  # Disable access logs (already logged by our middleware)
            timeout_keep_alive=5,  # Reduce keep-alive timeout
            timeout_graceful_shutdown=10  # Add graceful shutdown timeout
        )
    finally:
        if dbus_service:
            dbus_service.stop()


if __name__ == "__main__":
    main()
