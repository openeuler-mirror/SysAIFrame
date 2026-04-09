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

impl StreamIterator {
    pub(crate) fn new(connection: Connection, request_id: String, model: String) -> Result<Self> {
        let done = Arc::new(Mutex::new(false));
        let chunks = Arc::new(Mutex::new(Vec::new()));

        Ok(Self {
            connection,
            request_id,
            model,
            done,
            chunks,
            index: 0,
        })
    }
}