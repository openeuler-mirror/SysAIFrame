/*
 * SysAI Rust SDK - Client implementation
 *
 * Copyright (C) 2025 CTyunOS. All Rights Reserved.
 */

use crate::{ChatChunk, ChatOptions, ChatResponse, Message, Result, SysAIError};
use std::collections::HashMap;
use zbus::blocking::{Connection, Proxy};
use zbus::zvariant::{OwnedValue, Value};

const BUS_NAME: &str = "org.ctyunos.AIGateway.Chat";
const OBJECT_PATH: &str = "/org/ctyunos/AIGateway/Chat";
const INTERFACE: &str = "org.ctyunos.AIGateway.Chat";

/// Synchronous SysAI client
pub struct SysAIClient {
    connection: Connection,
}
