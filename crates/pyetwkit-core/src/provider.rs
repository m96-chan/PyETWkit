//! ETW Provider management

use crate::error::{EtwError, Result};
use crate::filter::EventFilter;
use pyo3::prelude::*;
use serde::{Deserialize, Serialize};
use std::str::FromStr;
use uuid::Uuid;

/// Trace level for event filtering
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[repr(u8)]
pub enum TraceLevel {
    /// Log always
    Always = 0,
    /// Critical errors
    Critical = 1,
    /// Errors
    Error = 2,
    /// Warnings
    Warning = 3,
    /// Informational
    Info = 4,
    /// Verbose/debug
    Verbose = 5,
}

impl Default for TraceLevel {
    fn default() -> Self {
        TraceLevel::Verbose
    }
}

impl From<u8> for TraceLevel {
    fn from(value: u8) -> Self {
        match value {
            0 => TraceLevel::Always,
            1 => TraceLevel::Critical,
            2 => TraceLevel::Error,
            3 => TraceLevel::Warning,
            4 => TraceLevel::Info,
            _ => TraceLevel::Verbose,
        }
    }
}

/// ETW Provider configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EtwProvider {
    /// Provider GUID
    pub guid: Uuid,
    /// Provider name (human-readable)
    pub name: Option<String>,
    /// Trace level
    pub level: TraceLevel,
    /// Keywords to match (any)
    pub keywords_any: u64,
    /// Keywords that must all match
    pub keywords_all: u64,
    /// Event filters
    pub filters: Vec<EventFilter>,
    /// Whether the provider is enabled
    pub enabled: bool,
    /// Capture stack traces for events
    pub capture_stack: bool,
}

impl EtwProvider {
    /// Create a new provider by GUID
    pub fn by_guid(guid: Uuid) -> Self {
        Self {
            guid,
            name: None,
            level: TraceLevel::default(),
            keywords_any: 0xFFFFFFFFFFFFFFFF,
            keywords_all: 0,
            filters: Vec::new(),
            enabled: true,
            capture_stack: false,
        }
    }

    /// Create a provider from GUID string
    pub fn from_guid_str(guid_str: &str) -> Result<Self> {
        let guid = Uuid::from_str(guid_str)
            .map_err(|_| EtwError::InvalidProviderGuid(guid_str.to_string()))?;
        Ok(Self::by_guid(guid))
    }

    /// Set provider name
    pub fn with_name(mut self, name: impl Into<String>) -> Self {
        self.name = Some(name.into());
        self
    }

    /// Set trace level
    pub fn with_level(mut self, level: TraceLevel) -> Self {
        self.level = level;
        self
    }

    /// Set keywords (any match)
    pub fn with_keywords_any(mut self, keywords: u64) -> Self {
        self.keywords_any = keywords;
        self
    }

    /// Set keywords (all must match)
    pub fn with_keywords_all(mut self, keywords: u64) -> Self {
        self.keywords_all = keywords;
        self
    }

    /// Add an event filter
    pub fn with_filter(mut self, filter: EventFilter) -> Self {
        self.filters.push(filter);
        self
    }

    /// Enable stack trace capture
    pub fn with_stack_trace(mut self, capture: bool) -> Self {
        self.capture_stack = capture;
        self
    }

    /// Check if this provider matches the given event criteria
    pub fn matches_event(&self, event_id: u16, opcode: u8, level: u8, keywords: u64) -> bool {
        // Level filter
        if level > self.level as u8 {
            return false;
        }

        // Keywords filter
        if self.keywords_any != 0 && (keywords & self.keywords_any) == 0 {
            return false;
        }
        if self.keywords_all != 0 && (keywords & self.keywords_all) != self.keywords_all {
            return false;
        }

        // Custom filters
        for filter in &self.filters {
            if !filter.matches(event_id, opcode) {
                return false;
            }
        }

        true
    }
}

/// Enable properties for tracing (e.g., stack traces)
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum EnableProperty {
    /// Enable stack trace capture
    StackTrace,
    /// Enable SID (Security Identifier) capture
    Sid,
    /// Enable terminal session ID
    TsId,
    /// Enable process start key
    ProcessStartKey,
}

impl EnableProperty {
    /// Get the Windows constant value
    pub fn value(&self) -> u32 {
        match self {
            EnableProperty::StackTrace => 0x00000001, // EVENT_ENABLE_PROPERTY_STACK_TRACE
            EnableProperty::Sid => 0x00000002,        // EVENT_ENABLE_PROPERTY_SID
            EnableProperty::TsId => 0x00000004,       // EVENT_ENABLE_PROPERTY_TS_ID
            EnableProperty::ProcessStartKey => 0x00000008, // EVENT_ENABLE_PROPERTY_PROCESS_START_KEY
        }
    }
}

/// Python wrapper for EnableProperty
#[pyclass(name = "EnableProperty")]
#[derive(Clone)]
pub struct PyEnableProperty;

#[pymethods]
impl PyEnableProperty {
    /// Stack trace capture flag
    #[classattr]
    #[pyo3(name = "STACK_TRACE")]
    fn stack_trace() -> u32 {
        EnableProperty::StackTrace.value()
    }

    /// SID capture flag
    #[classattr]
    #[pyo3(name = "SID")]
    fn sid() -> u32 {
        EnableProperty::Sid.value()
    }

    /// Terminal session ID capture flag
    #[classattr]
    #[pyo3(name = "TS_ID")]
    fn ts_id() -> u32 {
        EnableProperty::TsId.value()
    }

    /// Process start key capture flag
    #[classattr]
    #[pyo3(name = "PROCESS_START_KEY")]
    fn process_start_key() -> u32 {
        EnableProperty::ProcessStartKey.value()
    }
}

/// Well-known provider GUIDs
pub mod known_providers {
    use uuid::Uuid;

    /// Microsoft-Windows-Kernel-Process
    pub const KERNEL_PROCESS: Uuid = Uuid::from_u128(0x22fb2cd6_0e7b_422b_a0c7_2fad1fd0e716);

    /// Microsoft-Windows-Kernel-File
    pub const KERNEL_FILE: Uuid = Uuid::from_u128(0xedd08927_9cc4_4e65_b970_c2560fb5c289);

    /// Microsoft-Windows-Kernel-Network
    pub const KERNEL_NETWORK: Uuid = Uuid::from_u128(0x7dd42a49_5329_4832_8dfd_43d979153a88);

    /// Microsoft-Windows-Kernel-Registry
    pub const KERNEL_REGISTRY: Uuid = Uuid::from_u128(0x70eb4f03_c1de_4f73_a051_33d13d5413bd);

    /// Microsoft-Windows-DNS-Client
    pub const DNS_CLIENT: Uuid = Uuid::from_u128(0x1c95126e_7eea_49a9_a3fe_a378b03ddb4d);

    /// Microsoft-Windows-TCPIP
    pub const TCPIP: Uuid = Uuid::from_u128(0x2f07e2ee_15db_40f1_90ef_9d7ba282188a);

    /// Microsoft-Windows-Security-Auditing
    pub const SECURITY_AUDITING: Uuid = Uuid::from_u128(0x54849625_5478_4994_a5ba_3e3b0328c30d);

    /// Microsoft-Windows-PowerShell
    pub const POWERSHELL: Uuid = Uuid::from_u128(0xa0c1853b_5c40_4b15_8766_3cf1c58f985a);
}

/// Python wrapper for EtwProvider
#[pyclass(name = "EtwProvider")]
#[derive(Clone)]
pub struct PyEtwProvider {
    pub(crate) inner: EtwProvider,
}

#[pymethods]
impl PyEtwProvider {
    /// Create a provider from GUID string
    #[new]
    #[pyo3(signature = (guid, name=None))]
    fn new(guid: &str, name: Option<String>) -> PyResult<Self> {
        let mut provider = EtwProvider::from_guid_str(guid)?;
        if let Some(n) = name {
            provider = provider.with_name(n);
        }
        Ok(Self { inner: provider })
    }

    /// Create a provider for kernel process events
    #[staticmethod]
    fn kernel_process() -> Self {
        Self {
            inner: EtwProvider::by_guid(known_providers::KERNEL_PROCESS)
                .with_name("Microsoft-Windows-Kernel-Process"),
        }
    }

    /// Create a provider for DNS client events
    #[staticmethod]
    fn dns_client() -> Self {
        Self {
            inner: EtwProvider::by_guid(known_providers::DNS_CLIENT)
                .with_name("Microsoft-Windows-DNS-Client"),
        }
    }

    /// Create a provider for PowerShell events
    #[staticmethod]
    fn powershell() -> Self {
        Self {
            inner: EtwProvider::by_guid(known_providers::POWERSHELL)
                .with_name("Microsoft-Windows-PowerShell"),
        }
    }

    /// Provider GUID
    #[getter]
    fn guid(&self) -> String {
        self.inner.guid.to_string()
    }

    /// Provider name
    #[getter]
    fn name(&self) -> Option<String> {
        self.inner.name.clone()
    }

    /// Set trace level (0=Always to 5=Verbose)
    fn level(&mut self, level: u8) -> Self {
        self.inner.level = TraceLevel::from(level);
        self.clone()
    }

    /// Set keywords (any match)
    fn keywords_any(&mut self, keywords: u64) -> Self {
        self.inner.keywords_any = keywords;
        self.clone()
    }

    /// Set keywords (all must match)
    fn keywords_all(&mut self, keywords: u64) -> Self {
        self.inner.keywords_all = keywords;
        self.clone()
    }

    /// Filter by specific event IDs
    fn event_ids(&mut self, ids: Vec<u16>) -> Self {
        self.inner.filters.push(EventFilter::EventIds(ids));
        self.clone()
    }

    /// Filter by process ID
    fn process_id(&mut self, pid: u32) -> Self {
        self.inner.filters.push(EventFilter::ProcessId(pid));
        self.clone()
    }

    /// Enable stack trace capture
    fn stack_trace(&mut self, enabled: bool) -> Self {
        self.inner.capture_stack = enabled;
        self.clone()
    }

    fn __repr__(&self) -> String {
        format!(
            "EtwProvider(guid={}, name={:?})",
            self.inner.guid, self.inner.name
        )
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_provider_creation() {
        let provider = EtwProvider::by_guid(known_providers::KERNEL_PROCESS)
            .with_name("Test")
            .with_level(TraceLevel::Info);

        assert_eq!(provider.name, Some("Test".to_string()));
        assert_eq!(provider.level, TraceLevel::Info);
    }

    #[test]
    fn test_provider_from_guid_str() {
        let provider = EtwProvider::from_guid_str("22fb2cd6-0e7b-422b-a0c7-2fad1fd0e716").unwrap();
        assert_eq!(provider.guid, known_providers::KERNEL_PROCESS);
    }

    #[test]
    fn test_provider_invalid_guid() {
        let result = EtwProvider::from_guid_str("invalid-guid");
        assert!(result.is_err());
    }

    #[test]
    fn test_matches_event_level() {
        let provider = EtwProvider::by_guid(Uuid::new_v4()).with_level(TraceLevel::Warning);

        // Should match: level <= Warning (3)
        assert!(provider.matches_event(1, 0, 1, 0)); // Critical
        assert!(provider.matches_event(1, 0, 2, 0)); // Error
        assert!(provider.matches_event(1, 0, 3, 0)); // Warning

        // Should not match: level > Warning
        assert!(!provider.matches_event(1, 0, 4, 0)); // Info
        assert!(!provider.matches_event(1, 0, 5, 0)); // Verbose
    }

    #[test]
    fn test_matches_event_keywords() {
        let provider = EtwProvider::by_guid(Uuid::new_v4()).with_keywords_any(0x0F);

        assert!(provider.matches_event(1, 0, 0, 0x01)); // Matches any
        assert!(provider.matches_event(1, 0, 0, 0x08)); // Matches any
        assert!(!provider.matches_event(1, 0, 0, 0x10)); // No match
    }
}
