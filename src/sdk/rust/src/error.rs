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
    #[error("D-Bus connection failed: {0}")]
    Connection(String),

    #[error("Service not available: {0}")]
    ServiceUnavailable(String),

    #[error("Invalid request: {0}")]
    InvalidRequest(String),

    #[error("Request timeout: {0}")]
    Timeout(String),

    #[error("Model not found: {0}")]
    ModelNotFound(String),

    #[error("Server error: {0}")]
    Server(String),

    #[error("D-Bus error: {0}")]
    DBus(#[from] zbus::Error),

    #[error("Serialization error: {0}")]
    Serialization(#[from] serde_json::Error),

    #[error("Variant conversion error: {0}")]
    Variant(#[from] zvariant::Error),
}
