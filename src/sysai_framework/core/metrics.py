"""
Copyright (C) 2025 CTyunOS. All Rights Reserved.
File: metrics.py
Desc: Prometheus metrics for health checking and fallback monitoring
Date: 2026-01-16
Author: Liu Mingran
"""

from prometheus_client import Counter, Gauge, Histogram

# Health check metrics
health_check_total = Counter(
    'sysaiframe_health_check_total',
    'Total health check attempts',
    ['model', 'check_type']  # check_type: lightweight or actual_request
)

health_check_success = Counter(
    'sysaiframe_health_check_success',
    'Successful health checks',
    ['model', 'check_type']
)

health_check_failure = Counter(
    'sysaiframe_health_check_failure',
    'Failed health checks',
    ['model', 'check_type']
)

health_check_duration_seconds = Histogram(
    'sysaiframe_health_check_duration_seconds',
    'Health check duration in seconds',
    ['model', 'check_type'],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0]
)

# Model status metrics
model_healthy_status = Gauge(
    'sysaiframe_model_healthy',
    'Model health status (1=healthy, 0=unhealthy)',
    ['model', 'instance_id']
)

model_consecutive_failures = Gauge(
    'sysaiframe_model_consecutive_failures',
    'Number of consecutive failures for a model',
    ['model', 'instance_id']
)

model_consecutive_successes = Gauge(
    'sysaiframe_model_consecutive_successes',
    'Number of consecutive successes for a model',
    ['model', 'instance_id']
)

model_unhealthy_reason = Gauge(
    'sysaiframe_model_unhealthy_reason',
    'Reason for model being unhealthy (0=none, 1=lightweight, 2=actual_request)',
    ['model', 'instance_id']
)

# Fallback metrics
fallback_total = Counter(
    'sysaiframe_fallback_total',
    'Total number of fallback attempts',
    ['from_model', 'to_model', 'reason']  # reason: health, error, timeout
)

fallback_success = Counter(
    'sysaiframe_fallback_success',
    'Successful fallback attempts',
    ['from_model', 'to_model']
)

# Model request metrics
model_request_total = Counter(
    'sysaiframe_model_request_total',
    'Total model requests',
    ['model', 'status']  # status: success, retriable_error, non_retriable_error
)

model_request_duration_seconds = Histogram(
    'sysaiframe_model_request_duration_seconds',
    'Model request duration in seconds',
    ['model'],
    buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0]
)

# Retry metrics
retry_attempt_total = Counter(
    'sysaiframe_retry_attempt_total',
    'Total retry attempts',
    ['model', 'attempt_number']
)

retry_exhausted_total = Counter(
    'sysaiframe_retry_exhausted_total',
    'Total cases where all retries exhausted',
    ['model']
)

# Overall system metrics
all_models_failed_total = Counter(
    'sysaiframe_all_models_failed_total',
    'Total cases where all models (including fallbacks) failed',
    []
)

# Token usage metrics
token_usage_total = Counter(
    'sysaiframe_token_usage_total',
    'Total tokens consumed',
    ['model', 'token_type']  # token_type: prompt, completion
)

# Streaming metrics
streaming_chunks_total = Counter(
    'sysaiframe_streaming_chunks_total',
    'Total streaming chunks sent',
    ['model']
)
