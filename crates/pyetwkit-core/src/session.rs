//! ETW Session management using ferrisetw

use crate::error::{EtwError, Result};
use crate::event::{EtwEvent, EventValue, PyEtwEvent};
use crate::filter::EventFilter;
use crate::provider::{EtwProvider, PyEtwProvider, TraceLevel};
use crate::stats::{PySessionStats, SessionStats, SharedStatsTracker, StatsTracker};

use chrono::{TimeZone, Utc};
use crossbeam_channel::{bounded, Receiver, Sender, TrySendError};
use ferrisetw::parser::Parser;
use ferrisetw::provider::Provider;
use ferrisetw::schema::Schema;
use ferrisetw::schema_locator::SchemaLocator;
use ferrisetw::trace::{stop_trace_by_name, TraceTrait, UserTrace};
use ferrisetw::EventRecord;
use parking_lot::RwLock;
use pyo3::prelude::*;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;
use std::thread::{self, JoinHandle};
use std::time::Duration;
use uuid::Uuid;

/// Trace mode
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize, Default)]
pub enum TraceMode {
    /// Real-time trace (default)
    #[default]
    RealTime,
    /// Read from ETL file
    File,
}

/// Session configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SessionConfig {
    /// Session name (must be unique)
    pub name: String,
    /// Trace mode
    pub mode: TraceMode,
    /// Buffer size in KB (default: 64)
    pub buffer_size_kb: u32,
    /// Minimum number of buffers (default: 64)
    pub min_buffers: u32,
    /// Maximum number of buffers (default: 128)
    pub max_buffers: u32,
    /// Flush timer in seconds (default: 1)
    pub flush_timer_secs: u32,
    /// Stop if session already exists
    pub stop_if_exists: bool,
    /// Event channel capacity
    pub channel_capacity: usize,
}

impl Default for SessionConfig {
    fn default() -> Self {
        Self {
            name: format!(
                "PyETWkit-{}",
                Uuid::new_v4().to_string().split('-').next().unwrap()
            ),
            mode: TraceMode::RealTime,
            buffer_size_kb: 64,
            min_buffers: 64,
            max_buffers: 128,
            flush_timer_secs: 1,
            stop_if_exists: true,
            channel_capacity: 10000,
        }
    }
}

/// ETW Session state
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum SessionState {
    Created,
    Running,
    Stopped,
    Error,
}

/// Internal session handle
struct SessionHandle {
    trace: Option<UserTrace>,
    trace_thread: Option<JoinHandle<()>>,
    stop_flag: Arc<AtomicBool>,
}

/// ETW Session
pub struct EtwSession {
    config: SessionConfig,
    providers: Vec<EtwProvider>,
    state: Arc<RwLock<SessionState>>,
    event_rx: Option<Receiver<EtwEvent>>,
    event_tx: Option<Sender<EtwEvent>>,
    stats: SharedStatsTracker,
    handle: Option<SessionHandle>,
}

impl EtwSession {
    /// Create a new session with default configuration
    pub fn new(name: impl Into<String>) -> Self {
        let config = SessionConfig {
            name: name.into(),
            ..SessionConfig::default()
        };
        Self::with_config(config)
    }

    /// Create a new session with custom configuration
    pub fn with_config(config: SessionConfig) -> Self {
        let (tx, rx) = bounded(config.channel_capacity);
        let stats = Arc::new(StatsTracker::new(config.buffer_size_kb, config.min_buffers));

        Self {
            config,
            providers: Vec::new(),
            state: Arc::new(RwLock::new(SessionState::Created)),
            event_rx: Some(rx),
            event_tx: Some(tx),
            stats,
            handle: None,
        }
    }

    /// Add a provider to the session
    pub fn add_provider(&mut self, provider: EtwProvider) -> &mut Self {
        self.providers.push(provider);
        self
    }

    /// Start the trace session
    pub fn start(&mut self) -> Result<()> {
        let state = *self.state.read();
        if state == SessionState::Running {
            return Err(EtwError::SessionAlreadyRunning);
        }

        // Stop existing session if configured
        if self.config.stop_if_exists {
            let _ = stop_trace_by_name(&self.config.name);
        }

        // Build providers
        let mut trace_builder = UserTrace::new().named(self.config.name.clone());

        let event_tx = self
            .event_tx
            .clone()
            .ok_or(EtwError::Internal("No event channel".into()))?;
        let stats = self.stats.clone();
        let state_clone = self.state.clone();
        let stop_flag = Arc::new(AtomicBool::new(false));
        let stop_flag_clone = stop_flag.clone();

        // Create callback closure
        let callback = move |record: &EventRecord, schema_locator: &SchemaLocator| {
            stats.record_event_received();

            // Try to resolve schema (ferrisetw 1.2: event_schema returns Result)
            let schema = schema_locator.event_schema(record).ok();

            // Parse event
            let event = parse_event_record(record, schema.as_ref().map(|s| s.as_ref()));

            // Send to channel
            match event_tx.try_send(event) {
                Ok(_) => {
                    stats.record_event_processed();
                }
                Err(TrySendError::Full(_)) => {
                    stats.record_events_lost(1);
                }
                Err(TrySendError::Disconnected(_)) => {
                    // Channel closed, stop processing
                }
            }
        };

        // Add providers to trace
        for provider in &self.providers {
            // Convert UUID to GUID string format for ferrisetw
            let guid_str = provider.guid.to_string();
            let mut prov_builder =
                Provider::by_guid(guid_str.as_str()).add_callback(callback.clone());

            // Set trace level (ferrisetw 1.2: level() takes u8 directly)
            prov_builder = match provider.level {
                TraceLevel::Always => prov_builder.level(0),
                TraceLevel::Critical => prov_builder.level(1),
                TraceLevel::Error => prov_builder.level(2),
                TraceLevel::Warning => prov_builder.level(3),
                TraceLevel::Info => prov_builder.level(4),
                TraceLevel::Verbose => prov_builder.level(5),
            };

            // Set keywords
            if provider.keywords_any != 0xFFFFFFFFFFFFFFFF {
                prov_builder = prov_builder.any(provider.keywords_any);
            }
            if provider.keywords_all != 0 {
                prov_builder = prov_builder.all(provider.keywords_all);
            }

            // Add event ID filters
            for filter in &provider.filters {
                match filter {
                    EventFilter::EventIds(ids) => {
                        for &id in ids {
                            prov_builder = prov_builder
                                .add_filter(ferrisetw::provider::EventFilter::ByEventIds(vec![id]));
                        }
                    }
                    EventFilter::ProcessId(pid) => {
                        // ferrisetw 1.2 uses u16 for PIDs, truncate if necessary
                        if let Ok(pid16) = u16::try_from(*pid) {
                            prov_builder = prov_builder
                                .add_filter(ferrisetw::provider::EventFilter::ByPids(vec![pid16]));
                        }
                    }
                    _ => {}
                }
            }

            let built_provider = prov_builder.build();
            trace_builder = trace_builder.enable(built_provider);
        }

        // Start trace using start() to get the trace object and handle
        // ferrisetw 1.2 API: start() returns (UserTrace, TraceHandle)
        let (user_trace, trace_handle) = trace_builder
            .start()
            .map_err(|e| EtwError::StartTraceFailed(format!("{:?}", e)))?;

        // Spawn thread to process events using the handle
        let trace_thread = thread::spawn(move || {
            let _ = UserTrace::process_from_handle(trace_handle);
            *state_clone.write() = SessionState::Stopped;
        });

        *self.state.write() = SessionState::Running;
        self.handle = Some(SessionHandle {
            trace: Some(user_trace),
            trace_thread: Some(trace_thread),
            stop_flag: stop_flag_clone,
        });

        Ok(())
    }

    /// Stop the trace session
    pub fn stop(&mut self) -> Result<()> {
        let state = *self.state.read();
        if state != SessionState::Running {
            return Err(EtwError::SessionNotRunning);
        }

        // Set stop flag
        if let Some(ref handle) = self.handle {
            handle.stop_flag.store(true, Ordering::SeqCst);
        }

        // Stop the trace by taking and dropping the UserTrace object
        // This calls UserTrace::stop() via Drop trait
        if let Some(mut handle) = self.handle.take() {
            // Take the trace to stop it (Drop will call stop)
            if let Some(trace) = handle.trace.take() {
                // Explicitly stop the trace
                let _ = trace.stop();
            }

            // Wait for processing thread to finish
            if let Some(thread) = handle.trace_thread.take() {
                let _ = thread.join();
            }
        }

        *self.state.write() = SessionState::Stopped;

        Ok(())
    }

    /// Get the next event (blocking)
    pub fn next_event(&self) -> Option<EtwEvent> {
        self.event_rx.as_ref()?.recv().ok()
    }

    /// Get the next event with timeout
    pub fn next_event_timeout(&self, timeout: Duration) -> Option<EtwEvent> {
        self.event_rx.as_ref()?.recv_timeout(timeout).ok()
    }

    /// Try to get the next event (non-blocking)
    pub fn try_next_event(&self) -> Option<EtwEvent> {
        self.event_rx.as_ref()?.try_recv().ok()
    }

    /// Get current statistics
    pub fn stats(&self) -> SessionStats {
        self.stats.snapshot()
    }

    /// Check if session is running
    pub fn is_running(&self) -> bool {
        *self.state.read() == SessionState::Running
    }

    /// Get session name
    pub fn name(&self) -> &str {
        &self.config.name
    }
}

impl Drop for EtwSession {
    fn drop(&mut self) {
        if self.is_running() {
            let _ = self.stop();
        }
    }
}

/// Convert ferrisetw GUID to uuid Uuid
fn guid_to_uuid(guid: ferrisetw::GUID) -> Uuid {
    Uuid::from_u128(guid.to_u128())
}

/// Parse ferrisetw EventRecord to our EtwEvent
pub fn parse_event_record(record: &EventRecord, schema: Option<&Schema>) -> EtwEvent {
    // ferrisetw 1.2 API: Direct access to event fields
    let provider_id = guid_to_uuid(record.provider_id());

    let mut event = EtwEvent::new(provider_id, record.event_id());
    event.version = record.version();
    event.opcode = record.opcode();
    event.level = record.level();
    event.keywords = record.keyword();
    event.process_id = record.process_id();
    event.thread_id = record.thread_id();
    // task is not directly available in ferrisetw 1.2
    event.task = 0;

    // Parse timestamp
    let timestamp_100ns = record.raw_timestamp();
    // Windows FILETIME epoch is 1601-01-01, convert to Unix epoch
    let unix_100ns = timestamp_100ns - 116444736000000000i64;
    let secs = unix_100ns / 10_000_000;
    let nanos = ((unix_100ns % 10_000_000) * 100) as u32;
    event.timestamp = Utc
        .timestamp_opt(secs, nanos)
        .single()
        .unwrap_or_else(Utc::now);

    // Parse activity IDs
    let activity = record.activity_id();
    if activity != ferrisetw::GUID::zeroed() {
        event.activity_id = Some(guid_to_uuid(activity));
    }

    // Parse properties using schema if available
    if let Some(schema) = schema {
        let parser = Parser::create(record, schema);
        event.properties = parse_properties(&parser, schema);
        event.provider_name = Some(schema.provider_name().to_string());
    }
    // Note: raw_data extraction removed as user_buffer is private in ferrisetw 1.2

    event
}

/// Parse event properties from schema
/// Note: ferrisetw 1.2 made properties() private, so we can't enumerate properties.
/// Instead, we extract common known properties if they exist.
fn parse_properties(parser: &Parser, _schema: &Schema) -> HashMap<String, EventValue> {
    let mut properties = HashMap::new();

    // Try common property names that might exist in various events
    let common_props = [
        "ProcessId",
        "ThreadId",
        "ImageFileName",
        "ProcessName",
        "CommandLine",
        "FileName",
        "FilePath",
        "Message",
        "Data",
        "Status",
        "Result",
        "ErrorCode",
    ];

    for name in common_props {
        // Try different types for each property
        if let Ok(v) = parser.try_parse::<String>(name) {
            properties.insert(name.to_string(), EventValue::String(v));
        } else if let Ok(v) = parser.try_parse::<u64>(name) {
            properties.insert(name.to_string(), EventValue::U64(v));
        } else if let Ok(v) = parser.try_parse::<u32>(name) {
            properties.insert(name.to_string(), EventValue::U32(v));
        } else if let Ok(v) = parser.try_parse::<i64>(name) {
            properties.insert(name.to_string(), EventValue::I64(v));
        } else if let Ok(v) = parser.try_parse::<i32>(name) {
            properties.insert(name.to_string(), EventValue::I32(v));
        }
        // Skip if property doesn't exist or can't be parsed
    }

    properties
}

/// Python wrapper for EtwSession
#[pyclass(name = "EtwSession")]
pub struct PyEtwSession {
    inner: Option<EtwSession>,
}

#[pymethods]
impl PyEtwSession {
    /// Create a new session
    #[new]
    #[pyo3(signature = (name=None))]
    fn new(name: Option<String>) -> Self {
        let session = match name {
            Some(n) => EtwSession::new(n),
            None => EtwSession::with_config(SessionConfig::default()),
        };
        Self {
            inner: Some(session),
        }
    }

    /// Create a session with custom configuration
    #[staticmethod]
    #[pyo3(signature = (name=None, buffer_size_kb=64, min_buffers=64, max_buffers=128, channel_capacity=10000))]
    fn with_config(
        name: Option<String>,
        buffer_size_kb: u32,
        min_buffers: u32,
        max_buffers: u32,
        channel_capacity: usize,
    ) -> Self {
        let mut config = SessionConfig::default();
        if let Some(n) = name {
            config.name = n;
        }
        config.buffer_size_kb = buffer_size_kb;
        config.min_buffers = min_buffers;
        config.max_buffers = max_buffers;
        config.channel_capacity = channel_capacity;

        Self {
            inner: Some(EtwSession::with_config(config)),
        }
    }

    /// Add a provider
    fn add_provider(&mut self, provider: PyEtwProvider) -> PyResult<()> {
        let session = self
            .inner
            .as_mut()
            .ok_or_else(|| pyo3::exceptions::PyRuntimeError::new_err("Session is closed"))?;
        session.add_provider(provider.inner.clone());
        Ok(())
    }

    /// Remove a provider by GUID string
    fn remove_provider(&mut self, guid: &str) -> PyResult<bool> {
        let session = self
            .inner
            .as_mut()
            .ok_or_else(|| pyo3::exceptions::PyRuntimeError::new_err("Session is closed"))?;

        let target_guid = Uuid::parse_str(guid)
            .map_err(|_| pyo3::exceptions::PyValueError::new_err("Invalid GUID format"))?;

        // Remove from internal provider list
        let original_len = session.providers.len();
        session.providers.retain(|p| p.guid != target_guid);

        Ok(session.providers.len() < original_len)
    }

    /// List all providers in this session
    fn list_providers(&self) -> PyResult<Vec<String>> {
        let session = self
            .inner
            .as_ref()
            .ok_or_else(|| pyo3::exceptions::PyRuntimeError::new_err("Session is closed"))?;

        Ok(session
            .providers
            .iter()
            .map(|p| p.guid.to_string())
            .collect())
    }

    /// Start the session
    fn start(&mut self) -> PyResult<()> {
        let session = self
            .inner
            .as_mut()
            .ok_or_else(|| pyo3::exceptions::PyRuntimeError::new_err("Session is closed"))?;
        session.start()?;
        Ok(())
    }

    /// Stop the session
    fn stop(&mut self) -> PyResult<()> {
        let session = self
            .inner
            .as_mut()
            .ok_or_else(|| pyo3::exceptions::PyRuntimeError::new_err("Session is closed"))?;
        session.stop()?;
        Ok(())
    }

    /// Get the next event (blocking)
    fn next_event(&self) -> PyResult<Option<PyEtwEvent>> {
        let session = self
            .inner
            .as_ref()
            .ok_or_else(|| pyo3::exceptions::PyRuntimeError::new_err("Session is closed"))?;
        Ok(session.next_event().map(PyEtwEvent::from))
    }

    /// Get the next event with timeout (in milliseconds)
    fn next_event_timeout(&self, timeout_ms: u64) -> PyResult<Option<PyEtwEvent>> {
        let session = self
            .inner
            .as_ref()
            .ok_or_else(|| pyo3::exceptions::PyRuntimeError::new_err("Session is closed"))?;
        Ok(session
            .next_event_timeout(Duration::from_millis(timeout_ms))
            .map(PyEtwEvent::from))
    }

    /// Try to get the next event (non-blocking)
    fn try_next_event(&self) -> PyResult<Option<PyEtwEvent>> {
        let session = self
            .inner
            .as_ref()
            .ok_or_else(|| pyo3::exceptions::PyRuntimeError::new_err("Session is closed"))?;
        Ok(session.try_next_event().map(PyEtwEvent::from))
    }

    /// Get session statistics
    fn stats(&self) -> PyResult<PySessionStats> {
        let session = self
            .inner
            .as_ref()
            .ok_or_else(|| pyo3::exceptions::PyRuntimeError::new_err("Session is closed"))?;
        Ok(PySessionStats::from(session.stats()))
    }

    /// Check if session is running
    fn is_running(&self) -> bool {
        self.inner.as_ref().map(|s| s.is_running()).unwrap_or(false)
    }

    /// Get session name
    #[getter]
    fn name(&self) -> Option<String> {
        self.inner.as_ref().map(|s| s.name().to_string())
    }

    /// Context manager enter
    fn __enter__(slf: PyRef<'_, Self>) -> PyRef<'_, Self> {
        slf
    }

    /// Context manager exit
    #[pyo3(signature = (_exc_type=None, _exc_val=None, _exc_tb=None))]
    fn __exit__(
        &mut self,
        _exc_type: Option<PyObject>,
        _exc_val: Option<PyObject>,
        _exc_tb: Option<PyObject>,
    ) -> PyResult<bool> {
        if let Some(ref mut session) = self.inner {
            if session.is_running() {
                let _ = session.stop();
            }
        }
        Ok(false)
    }

    fn __repr__(&self) -> String {
        match &self.inner {
            Some(session) => format!(
                "EtwSession(name={}, running={})",
                session.name(),
                session.is_running()
            ),
            None => "EtwSession(closed)".to_string(),
        }
    }
}

/// Register raw API functions for direct ETW access
pub fn register_raw_api(m: &Bound<'_, PyModule>) -> PyResult<()> {
    /// Stop a trace by name
    #[pyfunction]
    fn stop_trace(name: &str) -> PyResult<()> {
        stop_trace_by_name(name)
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(format!("{:?}", e)))?;
        Ok(())
    }

    m.add_function(wrap_pyfunction!(stop_trace, m)?)?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_session_config_default() {
        let config = SessionConfig::default();
        assert!(config.name.starts_with("PyETWkit-"));
        assert_eq!(config.buffer_size_kb, 64);
        assert_eq!(config.min_buffers, 64);
    }

    #[test]
    fn test_session_creation() {
        let session = EtwSession::new("TestSession");
        assert_eq!(session.name(), "TestSession");
        assert!(!session.is_running());
    }

    #[test]
    fn test_session_add_provider() {
        let mut session = EtwSession::new("TestSession");
        session.add_provider(EtwProvider::by_guid(Uuid::new_v4()));
        assert_eq!(session.providers.len(), 1);
    }
}
