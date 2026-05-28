/*
 * SysAI Rust SDK - Data types
 *
 * Copyright (C) 2025 CTyunOS. All Rights Reserved.
 */

use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use zvariant::{OwnedValue, Value};

/// Chat message
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Message {
    pub role: String,
    pub content: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub name: Option<String>,
}

impl Message {
    /// Create a new message
    pub fn new<R: Into<String>, C: Into<String>>(role: R, content: C) -> Self {
        Self {
            role: role.into(),
            content: content.into(),
            name: None,
        }
    }

    /// Create a user message
    pub fn user<S: Into<String>>(content: S) -> Self {
        Self::new("user", content)
    }

    /// Create a system message
    pub fn system<S: Into<String>>(content: S) -> Self {
        Self::new("system", content)
    }

    /// Create an assistant message
    pub fn assistant<S: Into<String>>(content: S) -> Self {
        Self::new("assistant", content)
    }
    
    /// Set the name field
    pub fn with_name<S: Into<String>>(mut self, name: S) -> Self {
        self.name = Some(name.into());
        self
    }
    
    /// Convert to D-Bus variant dictionary
    pub(crate) fn to_variant_dict(&self) -> HashMap<String, OwnedValue> {
        let mut map = HashMap::new();
        map.insert("role".to_string(), Value::new(&self.role).try_to_owned().unwrap());
        map.insert("content".to_string(), Value::new(&self.content).try_to_owned().unwrap());
        if let Some(ref name) = self.name {
            map.insert("name".to_string(), Value::new(name).try_to_owned().unwrap());
        }
        map
    }
}

/// Chat options (builder pattern)
#[derive(Debug, Clone, Default)]
pub struct ChatOptions {
    pub model: Option<String>,
    pub temperature: Option<f64>,
    pub max_tokens: Option<i32>,
    pub top_p: Option<f64>,
}

impl ChatOptions {
    /// Create new options
    pub fn new() -> Self {
        Self::default()
    }
    
    /// Set model
    pub fn model<S: Into<String>>(mut self, model: S) -> Self {
        self.model = Some(model.into());
        self
    }
    
    /// Set temperature
    pub fn temperature(mut self, temperature: f64) -> Self {
        self.temperature = Some(temperature);
        self
    }
    
    /// Set max tokens
    pub fn max_tokens(mut self, max_tokens: i32) -> Self {
        self.max_tokens = Some(max_tokens);
        self
    }
    
    /// Set top_p
    pub fn top_p(mut self, top_p: f64) -> Self {
        self.top_p = Some(top_p);
        self
    }
}

/// Token usage statistics
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Usage {
    pub prompt_tokens: i32,
    pub completion_tokens: i32,
    pub total_tokens: i32,
}

impl Default for Usage {
    fn default() -> Self {
        Self {
            prompt_tokens: 0,
            completion_tokens: 0,
            total_tokens: 0,
        }
    }
}

/// Chat response
#[derive(Debug, Clone)]
pub struct ChatResponse {
    pub id: String,
    pub model: String,
    content: String,
    pub finish_reason: Option<String>,
    pub usage: Usage,
}

impl ChatResponse {
    /// Get response content (first choice)
    pub fn content(&self) -> &str {
        &self.content
    }
    
    /// Parse from D-Bus variant dictionary
    pub(crate) fn from_variant_dict(dict: HashMap<String, OwnedValue>) -> crate::Result<Self> {
        let id = extract_string(&dict, "id").unwrap_or_default();
        let model = extract_string(&dict, "model").unwrap_or_default();
        
        // Extract content from choices[0].message.content
        let content = extract_content_from_choices(&dict).unwrap_or_default();
        let finish_reason = extract_finish_reason(&dict);
        
        // Extract usage
        let usage = extract_usage(&dict);
        
        Ok(Self {
            id,
            model,
            content,
            finish_reason,
            usage,
        })
    }
}

/// Chat chunk (streaming)
#[derive(Debug, Clone)]
pub struct ChatChunk {
    pub id: String,
    pub model: String,
    content: Option<String>,
    pub finish_reason: Option<String>,
}

impl ChatChunk {
    /// Get chunk content
    pub fn content(&self) -> Option<&str> {
        self.content.as_deref()
    }
    
    /// Parse from D-Bus variant dictionary
    #[allow(dead_code)]
    pub(crate) fn from_variant_dict(
        id: String,
        model: String,
        dict: HashMap<String, OwnedValue>,
    ) -> crate::Result<Self> {
        let content = extract_delta_content(&dict);
        let finish_reason = extract_finish_reason(&dict);
        
        Ok(Self {
            id,
            model,
            content,
            finish_reason,
        })
    }
}

// Helper: convert OwnedValue to clean serde_json::Value (unwrap zvariant wrappers)
pub(crate) fn to_json(v: &OwnedValue) -> serde_json::Value {
    let raw = serde_json::to_value(v).unwrap_or(serde_json::Value::Null);
    unwrap_zvariant(raw)
}

fn unwrap_zvariant(v: serde_json::Value) -> serde_json::Value {
    match v {
        serde_json::Value::Object(ref map)
            if map.contains_key("zvariant::Value::Value") =>
        {
            let inner = map["zvariant::Value::Value"].clone();
            unwrap_zvariant(inner)
        }
        serde_json::Value::Object(map) => {
            serde_json::Value::Object(
                map.into_iter()
                    .map(|(k, v)| (k, unwrap_zvariant(v)))
                    .collect(),
            )
        }
        serde_json::Value::Array(arr) => {
            serde_json::Value::Array(arr.into_iter().map(unwrap_zvariant).collect())
        }
        other => other,
    }
}

fn extract_string(dict: &HashMap<String, OwnedValue>, key: &str) -> Option<String> {
    let v = dict.get(key)?;
    let json = to_json(v);
    json.as_str().filter(|s| !s.is_empty()).map(|s| s.to_string())
}

fn extract_content_from_choices(dict: &HashMap<String, OwnedValue>) -> Option<String> {
    let choices = dict.get("choices")?;
    let json = to_json(choices);
    let content = json.as_array()?
        .first()?
        .get("message")?
        .get("content")?
        .as_str()?;
    if content.is_empty() { None } else { Some(content.to_string()) }
}

#[allow(dead_code)]
fn extract_delta_content(dict: &HashMap<String, OwnedValue>) -> Option<String> {
    let choices = dict.get("choices")?;
    let json = to_json(choices);
    let content = json.as_array()?
        .first()?
        .get("delta")?
        .get("content")?
        .as_str()?;
    if content.is_empty() { None } else { Some(content.to_string()) }
}

fn extract_finish_reason(dict: &HashMap<String, OwnedValue>) -> Option<String> {
    let choices = dict.get("choices")?;
    let json = to_json(choices);
    let reason = json.as_array()?
        .first()?
        .get("finish_reason")?
        .as_str()?;
    if reason.is_empty() { None } else { Some(reason.to_string()) }
}

fn extract_usage(dict: &HashMap<String, OwnedValue>) -> Usage {
    let v = match dict.get("usage") {
        Some(v) => v,
        None => return Usage::default(),
    };
    let json = to_json(v);
    let obj = match json.as_object() {
        Some(o) => o,
        None => return Usage::default(),
    };
    Usage {
        prompt_tokens: obj.get("prompt_tokens").and_then(|v| v.as_i64()).unwrap_or(0) as i32,
        completion_tokens: obj.get("completion_tokens").and_then(|v| v.as_i64()).unwrap_or(0) as i32,
        total_tokens: obj.get("total_tokens").and_then(|v| v.as_i64()).unwrap_or(0) as i32,
    }
}
