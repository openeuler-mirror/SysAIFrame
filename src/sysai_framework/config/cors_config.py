"""
Copyright (C) 2025 CTyunOS. All Rights Reserved.
File: cors_config.py
Desc: CORS configuration management for SysAIFrame
     Dynamic CORS and environment settings
Date: 2025-10-28
Author: Liu Mingran
"""

import os
import re
from typing import List, Optional, Dict, Any
from urllib.parse import urlparse


class Config:
    """Configuration management for SysAIFrame

    CORS Policy:
    - Default: Only allow local access (localhost, 127.0.0.1, etc.)
    - Test Mode: Allow remote access with TEST_MODE=true environment variable
    """

    def __init__(self, gateway_config: Optional[Dict[str, Any]] = None):
        """
        Initialize configuration

        Args:
            gateway_config: Gateway configuration dict from models.yaml with keys:
                - remote_access: bool (default: False)
                - port: int (default: 6000)
        """
        gc = gateway_config or {}
        self.remote_access = gc.get('remote_access', False)
        self.gateway_host = '0.0.0.0' if self.remote_access else '127.0.0.1'
        self.gateway_port = int(gc.get('port', 6000))
        self.debug = os.getenv('DEBUG', 'false').lower() == 'true'
        # Test mode allows remote access for cross-platform testing
        self.test_mode = os.getenv('TEST_MODE', 'false').lower() == 'true'
        self.allowed_remote_hosts = self._parse_allowed_hosts() if self.test_mode else []
        
    def get_cors_origins(self) -> List[str]:
        """Get CORS allowed origins - only local requests allowed"""
        
        # Check if all origins are allowed (development mode only)
        allow_all = os.getenv('CORS_ALLOW_ALL', 'false').lower() == 'true'
        if allow_all:
            return ["*"]
        
        # Default: only allow local requests, use dynamic validation
        return ["*"]  # Use wildcard but validate dynamically in middleware
    
    def get_cors_credentials(self) -> bool:
        """Get CORS credentials setting"""
        return os.getenv('CORS_CREDENTIALS', 'true').lower() == 'true'
    
    def get_cors_methods(self) -> List[str]:
        """Get CORS allowed methods"""
        methods_env = os.getenv('CORS_METHODS', 'GET,POST,PUT,DELETE,OPTIONS')
        return [method.strip() for method in methods_env.split(',')]
    
    def get_cors_headers(self) -> List[str]:
        """Get CORS allowed headers"""
        headers_env = os.getenv('CORS_HEADERS', 'Accept,Accept-Language,Content-Language,Content-Type,Authorization,X-Requested-With,Origin,Access-Control-Request-Method,Access-Control-Request-Headers')
        return [header.strip() for header in headers_env.split(',')]
    
    def _parse_allowed_hosts(self) -> List[str]:
        """Parse allowed remote hosts from environment variable"""
        hosts_env = os.getenv('CORS_ALLOWED_HOSTS', '')
        if not hosts_env:
            return []
        
        # Support comma-separated list
        hosts = [h.strip() for h in hosts_env.split(',') if h.strip()]
        return hosts
    
    def get_allowed_remote_hosts(self) -> List[str]:
        """Get list of allowed remote hosts"""
        return self.allowed_remote_hosts
    
    def is_origin_allowed(self, origin: str) -> bool:
        """Check if an origin is allowed
        
        Policy:
        - Always allow local origins (localhost, 127.0.0.1, etc.)
        - Only allow remote origins when TEST_MODE=true
        """
        if not origin:
            return False
        
        # Always allow local origins
        if self._is_local_origin(origin):
            return True
        
        # Only allow remote access in test mode
        if self.test_mode:
            return self._is_remote_origin_allowed(origin)
        
        # Default: reject all remote origins
        return False
    
    def _is_local_origin(self, origin: str) -> bool:
        """Check if origin is a local application - strict local-only policy"""
        if not origin:
            return False
        
        try:
            parsed = urlparse(origin)
            hostname = parsed.hostname
            scheme = parsed.scheme
            
            # Check if it's a local file protocol (priority check)
            if scheme in ['file', 'app']:
                return True
            
            if not hostname:
                return False
            
            # Only allow true local addresses
            local_hostnames = {
                'localhost', '127.0.0.1', '0.0.0.0', '::1'
            }
            
            # Check if it's a local loopback address
            if hostname in local_hostnames:
                return True
            
            # Check if it's a local development domain
            if hostname.endswith('.local') or hostname.endswith('.localhost'):
                return True
                
        except Exception:
            pass
        
        return False
    
    def _is_remote_origin_allowed(self, origin: str) -> bool:
        """Check if remote origin is in allowed hosts list
        
        If CORS_ALLOWED_HOSTS is not set (empty list), allow all remote hosts in test mode.
        If CORS_ALLOWED_HOSTS is set, only allow hosts in the list.
        """
        if not origin:
            return False
        
        try:
            parsed = urlparse(origin)
            hostname = parsed.hostname
            
            if not hostname:
                return False
            
            # If no allowed hosts specified, allow all in test mode
            if not self.allowed_remote_hosts:
                return True
            
            # Check against allowed hosts list
            for allowed_host in self.allowed_remote_hosts:
                # Support exact match
                if hostname == allowed_host:
                    return True
                
                # Support wildcard pattern (e.g., *.example.com)
                if '*' in allowed_host:
                    pattern = allowed_host.replace('.', r'\.').replace('*', r'.*')
                    if re.match(pattern, hostname):
                        return True
                
                # Support IP address range (simple check)
                if hostname.startswith(allowed_host):
                    return True
            
            return False
                
        except Exception:
            return False


# Global configuration instance - created by main.py after ModelConfigManager initialization
config: Optional[Config] = None
