/*
 * SysAI Rust SDK - Streaming support
 *
 * Copyright (C) 2025 CTyunOS. All Rights Reserved.
 */

use crate::{ChatChunk, Result, SysAIError};
use std::sync::{Arc, Mutex};
use std::time::Duration;
use zbus::blocking::Connection;

const INTERFACE: &str = "org.ctyunos.AIGateway.Chat";
#[allow(dead_code)]
const OBJECT_PATH: &str = "/org/ctyunos/AIGateway/Chat";

/// Iterator for streaming chat chunks
pub struct StreamIterator {
    connection: Connection,
    request_id: String,
    model: String,
    done: Arc<Mutex<bool>>,
    chunks: Arc<Mutex<Vec<ChatChunk>>>,
    index: usize,
}