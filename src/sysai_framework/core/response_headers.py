"""
Copyright (C) 2025 CTyunOS. All Rights Reserved.
File: response_headers.py
Desc: Response header management for SysAIFrame
     Custom headers for debugging, monitoring and tracking
Date: 2025-10-22
Author: Liu Mingran
"""

from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)


class ResponseHeaderManager:
    """Response header manager - unified custom header management"""

    @staticmethod
    def get_custom_headers(
        request_id: Optional[str] = None,
        model_name: Optional[str] = None,
        provider: Optional[str] = None,
        duration_ms: Optional[float] = None,
        token_usage: Optional[Dict[str, int]] = None,
        cache_hit: bool = False,
        model_region: Optional[str] = None,
        api_version: str = "v1",
        response_cost: Optional[float] = None,
        original_cost: Optional[float] = None,
        discount_amount: Optional[float] = None,
        rate_limit_info: Optional[Dict[str, Any]] = None,
        overhead_ms: Optional[float] = None,
        backend_duration_ms: Optional[float] = None,
        model_id: Optional[str] = None,
        deployment_id: Optional[str] = None,
        cache_key: Optional[str] = None,
        user_limits: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Dict[str, str]:
        """
        Generate custom response headers

        Args:
            request_id: Unique request identifier
            model_name: Name of the model used
            provider: Model provider (e.g., openai, deepseek)
            duration_ms: Total response duration in milliseconds
            token_usage: Token usage information
            cache_hit: Whether response was from cache
            model_region: Model deployment region
            api_version: API version
            response_cost: Total cost of the response
            original_cost: Original cost before discounts
            discount_amount: Discount amount applied
            rate_limit_info: Rate limit information dict
            overhead_ms: Gateway overhead duration
            backend_duration_ms: Backend processing duration
            model_id: Internal model ID
            deployment_id: Deployment identifier
            cache_key: Cache key used
            user_limits: User-specific limits dict
            **kwargs: Additional custom headers

        Returns:
            Dictionary of custom headers
        """
        headers = {
            # Basic information
            "X-Request-ID": request_id,
            "X-Model-Name": model_name,
            "X-Model-ID": model_id,
            "X-Model-Provider": provider,
            "X-Model-Region": model_region,
            "X-Deployment-ID": deployment_id,
            "X-API-Version": api_version,
            "X-Gateway": "SysAIFrame",

            # Performance metrics
            "X-Response-Duration-MS": str(int(duration_ms)) if duration_ms else None,
            "X-Backend-Duration-MS": str(int(backend_duration_ms)) if backend_duration_ms else None,
            "X-Overhead-Duration-MS": str(int(overhead_ms)) if overhead_ms else None,

            # Cache information
            "X-Cache-Hit": str(cache_hit).lower(),
            "X-Cache-Key": cache_key,

            # Cost information
            "X-Response-Cost": f"{response_cost:.6f}" if response_cost is not None else None,
            "X-Response-Cost-Original": f"{original_cost:.6f}" if original_cost is not None else None,
            "X-Response-Cost-Discount": f"{discount_amount:.6f}" if discount_amount is not None else None,
        }

        # Token usage information
        if token_usage:
            headers.update({
                "X-Prompt-Tokens": str(token_usage.get("prompt_tokens", 0)),
                "X-Completion-Tokens": str(token_usage.get("completion_tokens", 0)),
                "X-Total-Tokens": str(token_usage.get("total_tokens", 0)),
            })

        # Rate limiting information
        if rate_limit_info:
            headers.update({
                "X-RateLimit-Limit-Requests": str(rate_limit_info.get("limit_requests", "")),
                "X-RateLimit-Limit-Tokens": str(rate_limit_info.get("limit_tokens", "")),
                "X-RateLimit-Remaining-Requests": str(rate_limit_info.get("remaining_requests", "")),
                "X-RateLimit-Remaining-Tokens": str(rate_limit_info.get("remaining_tokens", "")),
                "X-RateLimit-Reset": str(rate_limit_info.get("reset_time", "")),
            })

        # User limits information
        if user_limits:
            headers.update({
                "X-User-TPM-Limit": str(user_limits.get("tpm_limit", "")),
                "X-User-RPM-Limit": str(user_limits.get("rpm_limit", "")),
                "X-User-Max-Budget": str(user_limits.get("max_budget", "")),
                "X-User-Current-Spend": f"{user_limits.get('current_spend', 0):.6f}" if user_limits.get('current_spend') is not None else "",
            })

        # Additional custom headers
        for key, value in kwargs.items():
            if key.startswith("X-") or key.startswith("x-"):
                headers[key] = str(value) if value is not None else None

        # Filter out None and empty values
        return {k: v for k, v in headers.items() if v not in [None, "", "None"]}

    @staticmethod
    def get_streaming_headers(
        request_id: Optional[str] = None,
        model_name: Optional[str] = None,
        **kwargs
    ) -> Dict[str, str]:
        """
        Get headers specific for streaming responses

        Args:
            request_id: Unique request identifier
            model_name: Name of the model used
            **kwargs: Additional headers

        Returns:
            Dictionary of streaming-specific headers
        """
        base_headers = {
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
            "Content-Type": "text/event-stream",
        }

        # Add custom headers
        custom_headers = ResponseHeaderManager.get_custom_headers(
            request_id=request_id,
            model_name=model_name,
            **kwargs
        )

        # Merge headers
        base_headers.update(custom_headers)
        return base_headers

    @staticmethod
    def add_cors_headers(
        headers: Dict[str, str],
        allow_origin: str = "*",
        allow_methods: str = "GET, POST, OPTIONS",
        allow_headers: str = "*"
    ) -> Dict[str, str]:
        """
        Add CORS headers to response

        Args:
            headers: Existing headers dictionary
            allow_origin: Allowed origins
            allow_methods: Allowed HTTP methods
            allow_headers: Allowed headers

        Returns:
            Headers with CORS added
        """
        cors_headers = {
            "Access-Control-Allow-Origin": allow_origin,
            "Access-Control-Allow-Methods": allow_methods,
            "Access-Control-Allow-Headers": allow_headers,
            "Access-Control-Expose-Headers": ", ".join([
                k for k in headers.keys() if k.startswith("X-")
            ])
        }

        headers.update(cors_headers)
        return headers

    @staticmethod
    def get_error_headers(
        request_id: Optional[str] = None,
        error_code: Optional[str] = None,
        retry_after: Optional[int] = None
    ) -> Dict[str, str]:
        """
        Get headers for error responses

        Args:
            request_id: Request identifier
            error_code: Error code
            retry_after: Seconds to wait before retry (for rate limiting)

        Returns:
            Error-specific headers
        """
        headers = {
            "X-Request-ID": request_id,
            "X-Error-Code": error_code,
        }

        if retry_after is not None:
            headers["Retry-After"] = str(retry_after)

        return {k: v for k, v in headers.items() if v is not None}
