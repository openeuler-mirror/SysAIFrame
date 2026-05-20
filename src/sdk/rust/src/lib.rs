/*
 * SysAI Rust SDK - Library entry point
 *
 * Copyright (C) 2025 CTyunOS. All Rights Reserved.
 */

//! # SysAI Rust SDK
//!
//! Rust client library for SysAIFrame AI Gateway via D-Bus.

mod client;
mod error;
mod streaming;
mod types;

pub use client::SysAIClient;
pub use error::{Result, SysAIError};
pub use types::{ChatChunk, ChatOptions, ChatResponse, Message, Usage};

pub use zbus;
pub use zvariant;
