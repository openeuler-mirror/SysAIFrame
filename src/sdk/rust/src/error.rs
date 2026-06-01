/*
 * SysAI Rust SDK - Error types
 *
 * Copyright (C) 2025 CTyunOS. All Rights Reserved.
 */

use thiserror::Error;

/// Result type for SysAI SDK operations
pub type Result<T> = std::result::Result<T, SysAIError>;

/// Error types for SysAI SDK
#[derive(Error, Debug)]
pub enum SysAIError {
    /// D-Bus connection failed
    #[error("D-Bus connection failed: {0}")]
    Connection(String),

    /// Service not available
    #[error("Service not available: {0}")]
    ServiceUnavailable(String),

    /// Invalid request parameters
    #[error("Invalid request: {0}")]
    InvalidRequest(String),

    /// Request timeout
    #[error("Request timeout: {0}")]
    Timeout(String),

    /// Model not found
    #[error("Model not found: {0}")]
    ModelNotFound(String),

    /// Server internal error
    #[error("Server error: {0}")]
    Server(String),

    /// D-Bus error
    #[error("D-Bus error: {0}")]
    DBus(#[from] zbus::Error),

    /// Serialization error
    #[error("Serialization error: {0}")]
    Serialization(#[from] serde_json::Error),

    /// Variant conversion error
    #[error("Variant conversion error: {0}")]
    Variant(#[from] zvariant::Error),
}

impl SysAIError {
    /// Create a connection error
    pub fn connection<S: Into<String>>(msg: S) -> Self {
        Self::Connection(msg.into())
    }

    /// Create a service unavailable error
    pub fn service_unavailable<S: Into<String>>(msg: S) -> Self {
        Self::ServiceUnavailable(msg.into())
    }

    /// Create an invalid request error
    pub fn invalid_request<S: Into<String>>(msg: S) -> Self {
        Self::InvalidRequest(msg.into())
    }

    /// Create a timeout error
    pub fn timeout<S: Into<String>>(msg: S) -> Self {
        Self::Timeout(msg.into())
    }

    /// Create a model not found error
    pub fn model_not_found<S: Into<String>>(msg: S) -> Self {
        Self::ModelNotFound(msg.into())
    }

    /// Create a server error
    pub fn server<S: Into<String>>(msg: S) -> Self {
        Self::Server(msg.into())
    }
}