//! Event schema and property information
//!
//! This module provides schema resolution for ETW events using TDH APIs.

use pyo3::prelude::*;
use std::collections::HashMap;

/// Property type enumeration
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum PropertyType {
    /// Null/empty value
    Null,
    /// String value
    String,
    /// Signed 8-bit integer
    Int8,
    /// Unsigned 8-bit integer
    UInt8,
    /// Signed 16-bit integer
    Int16,
    /// Unsigned 16-bit integer
    UInt16,
    /// Signed 32-bit integer
    Int32,
    /// Unsigned 32-bit integer
    UInt32,
    /// Signed 64-bit integer
    Int64,
    /// Unsigned 64-bit integer
    UInt64,
    /// Single precision float
    Float,
    /// Double precision float
    Double,
    /// Boolean
    Boolean,
    /// Binary data
    Binary,
    /// GUID
    Guid,
    /// Pointer (platform dependent size)
    Pointer,
    /// File time (100ns intervals since 1601)
    FileTime,
    /// System time
    SystemTime,
    /// Security identifier
    Sid,
    /// Hexadecimal integer
    HexInt32,
    /// Hexadecimal 64-bit integer
    HexInt64,
    /// Unknown type
    Unknown,
}

impl PropertyType {
    /// Get type name as string
    pub fn as_str(&self) -> &'static str {
        match self {
            PropertyType::Null => "null",
            PropertyType::String => "string",
            PropertyType::Int8 => "int8",
            PropertyType::UInt8 => "uint8",
            PropertyType::Int16 => "int16",
            PropertyType::UInt16 => "uint16",
            PropertyType::Int32 => "int32",
            PropertyType::UInt32 => "uint32",
            PropertyType::Int64 => "int64",
            PropertyType::UInt64 => "uint64",
            PropertyType::Float => "float",
            PropertyType::Double => "double",
            PropertyType::Boolean => "boolean",
            PropertyType::Binary => "binary",
            PropertyType::Guid => "guid",
            PropertyType::Pointer => "pointer",
            PropertyType::FileTime => "filetime",
            PropertyType::SystemTime => "systemtime",
            PropertyType::Sid => "sid",
            PropertyType::HexInt32 => "hexint32",
            PropertyType::HexInt64 => "hexint64",
            PropertyType::Unknown => "unknown",
        }
    }
}

/// Information about a single event property
#[derive(Debug, Clone)]
pub struct PropertyInfo {
    /// Property name
    pub name: String,
    /// Property type
    pub property_type: PropertyType,
    /// Property length (if fixed)
    pub length: Option<u32>,
    /// Is this an array property
    pub is_array: bool,
}

/// Event schema containing property definitions
#[derive(Debug, Clone)]
pub struct EventSchema {
    /// Provider GUID
    pub provider_id: String,
    /// Event ID
    pub event_id: u16,
    /// Event version
    pub version: u8,
    /// Event name (if available)
    pub event_name: Option<String>,
    /// Property definitions
    pub properties: Vec<PropertyInfo>,
    /// Schema type (manifest, MOF, TraceLogging)
    pub schema_type: SchemaType,
}

/// Type of schema
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum SchemaType {
    /// Manifest-based (XML)
    Manifest,
    /// MOF-based (legacy)
    Mof,
    /// TraceLogging (self-describing)
    TraceLogging,
    /// Unknown
    Unknown,
}

impl SchemaType {
    pub fn as_str(&self) -> &'static str {
        match self {
            SchemaType::Manifest => "manifest",
            SchemaType::Mof => "mof",
            SchemaType::TraceLogging => "tracelogging",
            SchemaType::Unknown => "unknown",
        }
    }
}

impl EventSchema {
    /// Get property names
    pub fn property_names(&self) -> Vec<&str> {
        self.properties.iter().map(|p| p.name.as_str()).collect()
    }

    /// Get property by name
    pub fn get_property(&self, name: &str) -> Option<&PropertyInfo> {
        self.properties.iter().find(|p| p.name == name)
    }
}

/// Schema cache for efficient lookups
pub struct SchemaCache {
    cache: HashMap<(String, u16, u8), EventSchema>,
}

impl SchemaCache {
    pub fn new() -> Self {
        Self {
            cache: HashMap::new(),
        }
    }

    pub fn get(&self, provider_id: &str, event_id: u16, version: u8) -> Option<&EventSchema> {
        self.cache
            .get(&(provider_id.to_string(), event_id, version))
    }

    pub fn insert(&mut self, schema: EventSchema) {
        let key = (schema.provider_id.clone(), schema.event_id, schema.version);
        self.cache.insert(key, schema);
    }

    pub fn clear(&mut self) {
        self.cache.clear();
    }

    pub fn len(&self) -> usize {
        self.cache.len()
    }

    pub fn is_empty(&self) -> bool {
        self.cache.is_empty()
    }
}

impl Default for SchemaCache {
    fn default() -> Self {
        Self::new()
    }
}

// Python bindings

/// Python wrapper for PropertyInfo
#[pyclass(name = "PropertyInfo")]
#[derive(Clone)]
pub struct PyPropertyInfo {
    inner: PropertyInfo,
}

#[pymethods]
impl PyPropertyInfo {
    /// Property name
    #[getter]
    fn name(&self) -> &str {
        &self.inner.name
    }

    /// Property type as string
    #[getter]
    fn property_type(&self) -> &str {
        self.inner.property_type.as_str()
    }

    /// Property length (if fixed)
    #[getter]
    fn length(&self) -> Option<u32> {
        self.inner.length
    }

    /// Is this an array property
    #[getter]
    fn is_array(&self) -> bool {
        self.inner.is_array
    }

    fn __repr__(&self) -> String {
        format!(
            "PropertyInfo(name='{}', type='{}', is_array={})",
            self.inner.name,
            self.inner.property_type.as_str(),
            self.inner.is_array
        )
    }
}

impl From<PropertyInfo> for PyPropertyInfo {
    fn from(info: PropertyInfo) -> Self {
        Self { inner: info }
    }
}

/// Python wrapper for EventSchema
#[pyclass(name = "EventSchema")]
#[derive(Clone)]
pub struct PyEventSchema {
    inner: EventSchema,
}

#[pymethods]
impl PyEventSchema {
    /// Provider GUID
    #[getter]
    fn provider_id(&self) -> &str {
        &self.inner.provider_id
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

    /// Event name
    #[getter]
    fn event_name(&self) -> Option<&str> {
        self.inner.event_name.as_deref()
    }

    /// Schema type
    #[getter]
    fn schema_type(&self) -> &str {
        self.inner.schema_type.as_str()
    }

    /// Get property names
    fn property_names(&self) -> Vec<String> {
        self.inner
            .properties
            .iter()
            .map(|p| p.name.clone())
            .collect()
    }

    /// Get all properties
    #[getter]
    fn properties(&self) -> Vec<PyPropertyInfo> {
        self.inner
            .properties
            .iter()
            .cloned()
            .map(PyPropertyInfo::from)
            .collect()
    }

    /// Get property by name
    fn get_property(&self, name: &str) -> Option<PyPropertyInfo> {
        self.inner
            .get_property(name)
            .cloned()
            .map(PyPropertyInfo::from)
    }

    fn __repr__(&self) -> String {
        format!(
            "EventSchema(provider='{}', event_id={}, properties={})",
            self.inner.provider_id,
            self.inner.event_id,
            self.inner.properties.len()
        )
    }
}

impl From<EventSchema> for PyEventSchema {
    fn from(schema: EventSchema) -> Self {
        Self { inner: schema }
    }
}

/// Python wrapper for SchemaCache
#[pyclass(name = "SchemaCache")]
pub struct PySchemaCache {
    inner: SchemaCache,
}

#[pymethods]
impl PySchemaCache {
    #[new]
    fn new() -> Self {
        Self {
            inner: SchemaCache::new(),
        }
    }

    /// Clear the cache
    fn clear(&mut self) {
        self.inner.clear();
    }

    /// Get cache size
    fn __len__(&self) -> usize {
        self.inner.len()
    }

    fn __repr__(&self) -> String {
        format!("SchemaCache(entries={})", self.inner.len())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_property_type_as_str() {
        assert_eq!(PropertyType::String.as_str(), "string");
        assert_eq!(PropertyType::Int32.as_str(), "int32");
        assert_eq!(PropertyType::Guid.as_str(), "guid");
    }

    #[test]
    fn test_schema_property_names() {
        let schema = EventSchema {
            provider_id: "test".to_string(),
            event_id: 1,
            version: 0,
            event_name: None,
            properties: vec![
                PropertyInfo {
                    name: "ProcessId".to_string(),
                    property_type: PropertyType::UInt32,
                    length: Some(4),
                    is_array: false,
                },
                PropertyInfo {
                    name: "ImageFileName".to_string(),
                    property_type: PropertyType::String,
                    length: None,
                    is_array: false,
                },
            ],
            schema_type: SchemaType::Manifest,
        };

        let names = schema.property_names();
        assert_eq!(names, vec!["ProcessId", "ImageFileName"]);
    }
}
