/*
 * SysAI Rust SDK - Library entry point
 *
 * Copyright (C) 2025 CTyunOS. All Rights Reserved.
 */

//! # SysAI Rust SDK
//!
//! Rust client library for SysAIFrame AI Gateway via D-Bus.
//!
//! ## Features
//!
//! - Synchronous and asynchronous APIs
//! - Streaming and non-streaming chat completion
//! - Type-safe D-Bus communication via zbus
//! - Builder pattern for options
//!
//! ## Examples
//!
//! ### Synchronous non-streaming chat
//!
//! ```no_run
//! use sysai_sdk::{SysAIClient, Message};
//!
//! let client = SysAIClient::new()?;
//! let response = client.chat(
//!     &[Message::user("Hello")],
//!     None,
//! )?;
//! println!("{}", response.content());
//! # Ok::<(), sysai_sdk::SysAIError>(())
//! ```
//!
//! ### Synchronous streaming chat
//!
//! ```no_run
//! use sysai_sdk::{SysAIClient, Message};
//!
//! let client = SysAIClient::new()?;
//! for chunk in client.chat_stream(&[Message::user("Tell me a story")], None)? {
//!     let chunk = chunk?;
//!     if let Some(content) = chunk.content() {
//!         print!("{}", content);
//!     }
//! }
//! # Ok::<(), sysai_sdk::SysAIError>(())
//! ```

mod client;
mod error;
mod streaming;
mod types;

pub use client::SysAIClient;
pub use error::{Result, SysAIError};
pub use types::{ChatChunk, ChatOptions, ChatResponse, Message, Usage};

// Re-export commonly used types
pub use zbus;
pub use zvariant;
