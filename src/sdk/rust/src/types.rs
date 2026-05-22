/*
 * SysAI Rust SDK - Data types
 *
 * Copyright (C) 2025 CTyunOS. All Rights Reserved.
 */

use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use zvariant::{OwnedValue, Value};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Message {
    pub role: String,
    pub content: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub name: Option<String>,
}

impl Message {
    pub fn new<R: Into<String>, C: Into<String>>(role: R, content: C) -> Self {
        Self {
            role: role.into(),
            content: content.into(),
            name: None,
        }
    }

    pub fn user<S: Into<String>>(content: S) -> Self {
        Self::new("user", content)
    }

    pub fn system<S: Into<String>>(content: S) -> Self {
        Self::new("system", content)
    }

    pub fn assistant<S: Into<String>>(content: S) -> Self {
        Self::new("assistant", content)
    }

    pub fn with_name<S: Into<String>>(mut self, name: S) -> Self {
        self.name = Some(name.into());
        self
    }

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

#[derive(Debug, Clone, Default)]
pub struct ChatOptions {
    pub model: Option<String>,
    pub temperature: Option<f64>,
    pub max_tokens: Option<i32>,
    pub top_p: Option<f64>,
}

impl ChatOptions {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn model<S: Into<String>>(mut self, model: S) -> Self {
        self.model = Some(model.into());
        self
    }

    pub fn temperature(mut self, temperature: f64) -> Self {
        self.temperature = Some(temperature);
        self
    }

    pub fn max_tokens(mut self, max_tokens: i32) -> Self {
        self.max_tokens = Some(max_tokens);
        self
    }

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
