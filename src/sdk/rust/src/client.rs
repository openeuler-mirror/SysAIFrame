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

impl SysAIClient {
    /// Create a new client connected to system bus
    pub fn new() -> Result<Self> {
        let connection = Connection::system()
            .map_err(|e| SysAIError::connection(format!("Failed to connect to system bus: {}", e)))?;
        Ok(Self { connection })
    }

    /// Create a new client connected to session bus
    pub fn with_session_bus() -> Result<Self> {
        let connection = Connection::session()
            .map_err(|e| SysAIError::connection(format!("Failed to connect to session bus: {}", e)))?;
        Ok(Self { connection })
    }

    /// Send a chat completion request (non-streaming)
    pub fn chat(&self, messages: &[Message], options: Option<ChatOptions>) -> Result<ChatResponse> {
        let request = build_request_dict(messages, options, false)?;

        let proxy = Proxy::new(
            &self.connection, BUS_NAME, OBJECT_PATH, INTERFACE,
        ).map_err(|e| SysAIError::connection(format!("Failed to create proxy: {}", e)))?;

        let reply = proxy
            .call_method("ChatCompletion", &(request,))
            .map_err(|e| {
                let msg = e.to_string();
                if msg.contains("ServiceUnknown") {
                    SysAIError::service_unavailable("SysAIFrame service not available")
                } else if msg.contains("Timeout") {
                    SysAIError::timeout("Request timeout")
                } else {
                    SysAIError::Server(format!("D-Bus call failed: {}", e))
                }
            })?;

        let response: HashMap<String, OwnedValue> = reply.body().deserialize()
            .map_err(|e| SysAIError::Server(format!("Failed to deserialize response: {}", e)))?;

        // Check for errors in response
        if let Some(error) = response.get("error") {
            let error_json = crate::types::to_json(error);
            if let Some(obj) = error_json.as_object() {
                let message = obj.get("message")
                    .and_then(|v| v.as_str())
                    .unwrap_or("Unknown error");

                if message.to_lowercase().contains("not found") {
                    return Err(SysAIError::model_not_found(message));
                } else if message.to_lowercase().contains("unavailable") {
                    return Err(SysAIError::service_unavailable(message));
                } else if message.to_lowercase().contains("invalid") {
                    return Err(SysAIError::invalid_request(message));
                } else {
                    return Err(SysAIError::server(message));
                }
            }
        }

        ChatResponse::from_variant_dict(response)
    }

    /// Send a chat completion request with streaming
    ///
    /// Returns an iterator over chat chunks
    pub fn chat_stream(
        &self,
        messages: &[Message],
        options: Option<ChatOptions>,
    ) -> Result<impl Iterator<Item = Result<ChatChunk>>> {
        let request = build_request_dict(messages, options, true)?;

        let proxy = Proxy::new(
            &self.connection, BUS_NAME, OBJECT_PATH, INTERFACE,
        ).map_err(|e| SysAIError::connection(format!("Failed to create proxy: {}", e)))?;

        let reply = proxy
            .call_method("ChatCompletion", &(request,))
            .map_err(|e| SysAIError::Server(format!("D-Bus call failed: {}", e)))?;

        let response: HashMap<String, OwnedValue> = reply.body().deserialize()
            .map_err(|e| SysAIError::Server(format!("Failed to deserialize response: {}", e)))?;

        let request_id = response
            .get("id")
            .and_then(|v| {
                let json = crate::types::to_json(v);
                json.as_str().map(|s| s.to_string())
            })
            .ok_or_else(|| SysAIError::server("No request_id in response"))?;

        let model = response
            .get("model")
            .and_then(|v| {
                let json = crate::types::to_json(v);
                json.as_str().map(|s| s.to_string())
            })
            .unwrap_or_else(|| "default".to_string());

        crate::streaming::StreamIterator::new(self.connection.clone(), request_id, model)
    }
}
