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
}
