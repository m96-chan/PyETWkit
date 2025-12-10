//! ETW Event structures and parsing

use chrono::{DateTime, Utc};
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use uuid::Uuid;

/// Represents a parsed ETW event
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EtwEvent {
    /// Provider GUID
    pub provider_id: Uuid,
    /// Provider name (if known)
    pub provider_name: Option<String>,
    /// Event ID
    pub event_id: u16,
    /// Event version
    pub version: u8,
    /// Event opcode
    pub opcode: u8,
    /// Event level (0=Always, 1=Critical, 2=Error, 3=Warning, 4=Info, 5=Verbose)
    pub level: u8,
    /// Event keyword mask
    pub keywords: u64,
    /// Process ID that generated the event
    pub process_id: u32,
    /// Thread ID that generated the event
    pub thread_id: u32,
    /// Timestamp when event was generated
    pub timestamp: DateTime<Utc>,
    /// Activity ID for correlation
    pub activity_id: Option<Uuid>,
    /// Related activity ID
    pub related_activity_id: Option<Uuid>,
    /// Event task
    pub task: u16,
    /// Channel
    pub channel: u8,
    /// Parsed event properties
    pub properties: HashMap<String, EventValue>,
    /// Raw event data (if schema parsing failed)
    pub raw_data: Option<Vec<u8>>,
    /// Stack trace (if enabled)
    pub stack_trace: Option<Vec<u64>>,
}

/// Represents a value in an ETW event property
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(untagged)]
pub enum EventValue {
    Null,
    Bool(bool),
    I8(i8),
    U8(u8),
    I16(i16),
    U16(u16),
    I32(i32),
    U32(u32),
    I64(i64),
    U64(u64),
    F32(f32),
    F64(f64),
    String(String),
    Binary(Vec<u8>),
    Guid(Uuid),
    Pointer(u64),
    FileTime(i64),
    SystemTime(DateTime<Utc>),
    Sid(String),
    Array(Vec<EventValue>),
    Struct(HashMap<String, EventValue>),
}

impl EtwEvent {
    /// Create a new EtwEvent with minimal required fields
    pub fn new(provider_id: Uuid, event_id: u16) -> Self {
        Self {
            provider_id,
            provider_name: None,
            event_id,
            version: 0,
            opcode: 0,
            level: 4, // Info
            keywords: 0,
            process_id: 0,
            thread_id: 0,
            timestamp: Utc::now(),
            activity_id: None,
            related_activity_id: None,
            task: 0,
            channel: 0,
            properties: HashMap::new(),
            raw_data: None,
            stack_trace: None,
        }
    }

    /// Get a property value by name
    pub fn get(&self, name: &str) -> Option<&EventValue> {
        self.properties.get(name)
    }

    /// Get a property as a string
    pub fn get_string(&self, name: &str) -> Option<String> {
        self.properties.get(name).and_then(|v| v.as_string())
    }

    /// Get a property as u32
    pub fn get_u32(&self, name: &str) -> Option<u32> {
        self.properties.get(name).and_then(|v| v.as_u32())
    }

    /// Get a property as u64
    pub fn get_u64(&self, name: &str) -> Option<u64> {
        self.properties.get(name).and_then(|v| v.as_u64())
    }

    /// Convert to JSON string
    pub fn to_json(&self) -> Result<String, serde_json::Error> {
        serde_json::to_string(self)
    }

    /// Convert to pretty JSON string
    pub fn to_json_pretty(&self) -> Result<String, serde_json::Error> {
        serde_json::to_string_pretty(self)
    }
}

impl EventValue {
    /// Try to convert to string
    pub fn as_string(&self) -> Option<String> {
        match self {
            EventValue::String(s) => Some(s.clone()),
            EventValue::Bool(b) => Some(b.to_string()),
            EventValue::I8(n) => Some(n.to_string()),
            EventValue::U8(n) => Some(n.to_string()),
            EventValue::I16(n) => Some(n.to_string()),
            EventValue::U16(n) => Some(n.to_string()),
            EventValue::I32(n) => Some(n.to_string()),
            EventValue::U32(n) => Some(n.to_string()),
            EventValue::I64(n) => Some(n.to_string()),
            EventValue::U64(n) => Some(n.to_string()),
            EventValue::F32(n) => Some(n.to_string()),
            EventValue::F64(n) => Some(n.to_string()),
            EventValue::Guid(g) => Some(g.to_string()),
            EventValue::Pointer(p) => Some(format!("0x{:x}", p)),
            _ => None,
        }
    }

    /// Try to convert to u32
    pub fn as_u32(&self) -> Option<u32> {
        match self {
            EventValue::U8(n) => Some(*n as u32),
            EventValue::U16(n) => Some(*n as u32),
            EventValue::U32(n) => Some(*n),
            EventValue::I8(n) if *n >= 0 => Some(*n as u32),
            EventValue::I16(n) if *n >= 0 => Some(*n as u32),
            EventValue::I32(n) if *n >= 0 => Some(*n as u32),
            _ => None,
        }
    }

    /// Try to convert to u64
    pub fn as_u64(&self) -> Option<u64> {
        match self {
            EventValue::U8(n) => Some(*n as u64),
            EventValue::U16(n) => Some(*n as u64),
            EventValue::U32(n) => Some(*n as u64),
            EventValue::U64(n) => Some(*n),
            EventValue::I8(n) if *n >= 0 => Some(*n as u64),
            EventValue::I16(n) if *n >= 0 => Some(*n as u64),
            EventValue::I32(n) if *n >= 0 => Some(*n as u64),
            EventValue::I64(n) if *n >= 0 => Some(*n as u64),
            EventValue::Pointer(p) => Some(*p),
            _ => None,
        }
    }

    /// Check if value is null
    pub fn is_null(&self) -> bool {
        matches!(self, EventValue::Null)
    }
}

/// Python wrapper for EtwEvent
#[pyclass(name = "EtwEvent")]
#[derive(Clone)]
pub struct PyEtwEvent {
    inner: EtwEvent,
}

#[pymethods]
impl PyEtwEvent {
    /// Provider GUID as string
    #[getter]
    fn provider_id(&self) -> String {
        self.inner.provider_id.to_string()
    }

    /// Provider name (if known)
    #[getter]
    fn provider_name(&self) -> Option<String> {
        self.inner.provider_name.clone()
    }

    /// Event ID
    #[getter]
    fn event_id(&self) -> u16 {
        self.inner.event_id
    }

    /// Event version
    #[getter]
    fn version(&self) -> u8 {
        self.inner.version
    }

    /// Event opcode
    #[getter]
    fn opcode(&self) -> u8 {
        self.inner.opcode
    }

    /// Event level
    #[getter]
    fn level(&self) -> u8 {
        self.inner.level
    }

    /// Event keywords
    #[getter]
    fn keywords(&self) -> u64 {
        self.inner.keywords
    }

    /// Process ID
    #[getter]
    fn process_id(&self) -> u32 {
        self.inner.process_id
    }

    /// Thread ID
    #[getter]
    fn thread_id(&self) -> u32 {
        self.inner.thread_id
    }

    /// Timestamp as ISO 8601 string
    #[getter]
    fn timestamp(&self) -> String {
        self.inner.timestamp.to_rfc3339()
    }

    /// Timestamp as Unix timestamp (seconds)
    #[getter]
    fn timestamp_unix(&self) -> i64 {
        self.inner.timestamp.timestamp()
    }

    /// Timestamp as Unix timestamp (nanoseconds)
    #[getter]
    fn timestamp_ns(&self) -> i64 {
        self.inner.timestamp.timestamp_nanos_opt().unwrap_or(0)
    }

    /// Activity ID
    #[getter]
    fn activity_id(&self) -> Option<String> {
        self.inner.activity_id.map(|id| id.to_string())
    }

    /// Related activity ID
    #[getter]
    fn related_activity_id(&self) -> Option<String> {
        self.inner.related_activity_id.map(|id| id.to_string())
    }

    /// Task ID
    #[getter]
    fn task(&self) -> u16 {
        self.inner.task
    }

    /// Channel
    #[getter]
    fn channel(&self) -> u8 {
        self.inner.channel
    }

    /// Get event properties as a dictionary
    #[getter]
    fn properties(&self, py: Python<'_>) -> PyResult<Py<PyDict>> {
        let dict = PyDict::new(py);
        for (key, value) in &self.inner.properties {
            dict.set_item(key, event_value_to_py(py, value)?)?;
        }
        Ok(dict.into())
    }

    /// Get a specific property by name
    fn get(&self, py: Python<'_>, name: &str) -> PyResult<Option<PyObject>> {
        match self.inner.properties.get(name) {
            Some(value) => Ok(Some(event_value_to_py(py, value)?)),
            None => Ok(None),
        }
    }

    /// Get a property as string, or None if not found/convertible
    fn get_string(&self, name: &str) -> Option<String> {
        self.inner.get_string(name)
    }

    /// Get a property as u32, or None if not found/convertible
    fn get_u32(&self, name: &str) -> Option<u32> {
        self.inner.get_u32(name)
    }

    /// Get a property as u64, or None if not found/convertible
    fn get_u64(&self, name: &str) -> Option<u64> {
        self.inner.get_u64(name)
    }

    /// Check if a property exists
    fn has_property(&self, name: &str) -> bool {
        self.inner.properties.contains_key(name)
    }

    /// Get stack trace addresses (if captured)
    #[getter]
    fn stack_trace(&self, py: Python<'_>) -> Option<Py<PyList>> {
        self.inner.stack_trace.as_ref().map(|trace| {
            PyList::new(py, trace.iter().map(|&addr| addr)).unwrap().into()
        })
    }

    /// Convert to JSON string
    fn to_json(&self) -> PyResult<String> {
        self.inner
            .to_json()
            .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))
    }

    /// Convert to pretty JSON string
    fn to_json_pretty(&self) -> PyResult<String> {
        self.inner
            .to_json_pretty()
            .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))
    }

    fn __repr__(&self) -> String {
        format!(
            "EtwEvent(provider={}, event_id={}, pid={}, timestamp={})",
            self.inner
                .provider_name
                .as_deref()
                .unwrap_or(&self.inner.provider_id.to_string()),
            self.inner.event_id,
            self.inner.process_id,
            self.inner.timestamp.to_rfc3339()
        )
    }

    fn __str__(&self) -> String {
        self.__repr__()
    }
}

impl From<EtwEvent> for PyEtwEvent {
    fn from(event: EtwEvent) -> Self {
        Self { inner: event }
    }
}

impl PyEtwEvent {
    pub fn inner(&self) -> &EtwEvent {
        &self.inner
    }
}

/// Convert EventValue to Python object
fn event_value_to_py(py: Python<'_>, value: &EventValue) -> PyResult<PyObject> {
    Ok(match value {
        EventValue::Null => py.None(),
        EventValue::Bool(b) => b.into_pyobject(py)?.into_any().unbind(),
        EventValue::I8(n) => n.into_pyobject(py)?.into_any().unbind(),
        EventValue::U8(n) => n.into_pyobject(py)?.into_any().unbind(),
        EventValue::I16(n) => n.into_pyobject(py)?.into_any().unbind(),
        EventValue::U16(n) => n.into_pyobject(py)?.into_any().unbind(),
        EventValue::I32(n) => n.into_pyobject(py)?.into_any().unbind(),
        EventValue::U32(n) => n.into_pyobject(py)?.into_any().unbind(),
        EventValue::I64(n) => n.into_pyobject(py)?.into_any().unbind(),
        EventValue::U64(n) => n.into_pyobject(py)?.into_any().unbind(),
        EventValue::F32(n) => n.into_pyobject(py)?.into_any().unbind(),
        EventValue::F64(n) => n.into_pyobject(py)?.into_any().unbind(),
        EventValue::String(s) => s.into_pyobject(py)?.into_any().unbind(),
        EventValue::Binary(b) => b.as_slice().into_pyobject(py)?.into_any().unbind(),
        EventValue::Guid(g) => g.to_string().into_pyobject(py)?.into_any().unbind(),
        EventValue::Pointer(p) => p.into_pyobject(py)?.into_any().unbind(),
        EventValue::FileTime(ft) => ft.into_pyobject(py)?.into_any().unbind(),
        EventValue::SystemTime(st) => st.to_rfc3339().into_pyobject(py)?.into_any().unbind(),
        EventValue::Sid(s) => s.into_pyobject(py)?.into_any().unbind(),
        EventValue::Array(arr) => {
            let list = PyList::empty(py);
            for item in arr {
                list.append(event_value_to_py(py, item)?)?;
            }
            list.into()
        }
        EventValue::Struct(map) => {
            let dict = PyDict::new(py);
            for (k, v) in map {
                dict.set_item(k, event_value_to_py(py, v)?)?;
            }
            dict.into()
        }
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_event_creation() {
        let event = EtwEvent::new(Uuid::new_v4(), 100);
        assert_eq!(event.event_id, 100);
        assert_eq!(event.level, 4);
    }

    #[test]
    fn test_event_value_as_string() {
        assert_eq!(
            EventValue::String("test".to_string()).as_string(),
            Some("test".to_string())
        );
        assert_eq!(EventValue::U32(42).as_string(), Some("42".to_string()));
        assert_eq!(EventValue::Bool(true).as_string(), Some("true".to_string()));
    }

    #[test]
    fn test_event_value_as_u64() {
        assert_eq!(EventValue::U64(100).as_u64(), Some(100));
        assert_eq!(EventValue::U32(50).as_u64(), Some(50));
        assert_eq!(EventValue::String("test".to_string()).as_u64(), None);
    }

    #[test]
    fn test_event_json_serialization() {
        let mut event = EtwEvent::new(Uuid::nil(), 1);
        event.properties.insert(
            "Message".to_string(),
            EventValue::String("Hello".to_string()),
        );

        let json = event.to_json().unwrap();
        assert!(json.contains("\"event_id\":1"));
        assert!(json.contains("\"Message\":\"Hello\""));
    }
}
