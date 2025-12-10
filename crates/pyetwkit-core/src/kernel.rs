//! Kernel Logger (NT Kernel Logger) support
//!
//! The NT Kernel Logger is a special ETW session that provides kernel-level
//! events such as process, thread, file I/O, network, and disk events.
//!
//! Unlike regular providers, kernel events use special EVENT_TRACE_FLAG_*
//! flags instead of provider GUIDs.

use crate::error::{EtwError, Result};
use crate::event::EtwEvent;
use crate::stats::{SharedStatsTracker, StatsTracker};

use crossbeam_channel::{bounded, Receiver, Sender, TrySendError};
use ferrisetw::trace::{KernelTrace, TraceTrait, stop_trace_by_name};
use ferrisetw::schema_locator::SchemaLocator;
use ferrisetw::EventRecord;
use parking_lot::RwLock;
use pyo3::prelude::*;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;
use std::thread::{self, JoinHandle};
use std::time::Duration;

/// Kernel event categories
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
#[repr(u32)]
pub enum KernelEventCategory {
    /// Process creation and deletion
    Process = 0x00000001,
    /// Thread creation and deletion
    Thread = 0x00000002,
    /// Image load
    ImageLoad = 0x00000004,
    /// Disk I/O
    DiskIo = 0x00000100,
    /// Disk file I/O
    DiskFileIo = 0x00000200,
    /// Memory page faults
    PageFault = 0x00001000,
    /// Memory hard faults
    HardFault = 0x00002000,
    /// Network TCP/IP
    Network = 0x00010000,
    /// Registry
    Registry = 0x00020000,
    /// File I/O
    FileIo = 0x02000000,
    /// File I/O init
    FileIoInit = 0x04000000,
    /// Split I/O
    SplitIo = 0x00200000,
    /// Pool allocation
    Pool = 0x00400000,
    /// DPC
    Dpc = 0x00000020,
    /// Interrupt
    Interrupt = 0x00000040,
    /// System call
    SystemCall = 0x00000080,
    /// All basic events
    AllBasic = 0x00000007, // Process | Thread | ImageLoad
    /// All events
    All = 0xFFFFFFFF,
}

impl KernelEventCategory {
    /// Convert to ferrisetw KernelProvider flags
    pub fn to_flags(&self) -> u32 {
        *self as u32
    }

    /// Combine multiple categories
    pub fn combine(categories: &[KernelEventCategory]) -> u32 {
        categories.iter().fold(0u32, |acc, cat| acc | cat.to_flags())
    }
}

/// Kernel trace session state
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum KernelSessionState {
    Created,
    Running,
    Stopped,
    Error,
}

/// Kernel trace session configuration
#[derive(Debug, Clone)]
pub struct KernelSessionConfig {
    /// Session name (must be unique, defaults to "PyETWkit-Kernel")
    pub name: String,
    /// Event categories to enable
    pub categories: u32,
    /// Buffer size in KB
    pub buffer_size_kb: u32,
    /// Minimum number of buffers
    pub min_buffers: u32,
    /// Maximum number of buffers
    pub max_buffers: u32,
    /// Stop existing session if it exists
    pub stop_if_exists: bool,
    /// Event channel capacity
    pub channel_capacity: usize,
}

impl Default for KernelSessionConfig {
    fn default() -> Self {
        Self {
            name: "PyETWkit-Kernel".to_string(),
            categories: KernelEventCategory::AllBasic as u32,
            buffer_size_kb: 64,
            min_buffers: 64,
            max_buffers: 128,
            stop_if_exists: true,
            channel_capacity: 10000,
        }
    }
}

/// Internal handle for kernel trace
struct KernelHandle {
    trace_thread: Option<JoinHandle<()>>,
    stop_flag: Arc<AtomicBool>,
}

/// Kernel trace session
pub struct KernelSession {
    config: KernelSessionConfig,
    state: Arc<RwLock<KernelSessionState>>,
    event_rx: Option<Receiver<EtwEvent>>,
    event_tx: Option<Sender<EtwEvent>>,
    stats: SharedStatsTracker,
    handle: Option<KernelHandle>,
}

impl KernelSession {
    /// Create a new kernel session with default configuration
    pub fn new() -> Self {
        Self::with_config(KernelSessionConfig::default())
    }

    /// Create a new kernel session with custom configuration
    pub fn with_config(config: KernelSessionConfig) -> Self {
        let (tx, rx) = bounded(config.channel_capacity);
        let stats = Arc::new(StatsTracker::new(config.buffer_size_kb, config.min_buffers));

        Self {
            config,
            state: Arc::new(RwLock::new(KernelSessionState::Created)),
            event_rx: Some(rx),
            event_tx: Some(tx),
            stats,
            handle: None,
        }
    }

    /// Enable specific kernel event categories
    pub fn enable_category(&mut self, category: KernelEventCategory) -> &mut Self {
        self.config.categories |= category.to_flags();
        self
    }

    /// Set categories from flags
    pub fn set_categories(&mut self, flags: u32) -> &mut Self {
        self.config.categories = flags;
        self
    }

    /// Start the kernel trace session
    pub fn start(&mut self) -> Result<()> {
        let state = *self.state.read();
        if state == KernelSessionState::Running {
            return Err(EtwError::SessionAlreadyRunning);
        }

        // Stop existing session if configured
        if self.config.stop_if_exists {
            // The kernel logger session has a well-known name
            let _ = stop_trace_by_name("NT Kernel Logger");
            let _ = stop_trace_by_name(&self.config.name);
        }

        let event_tx = self.event_tx.clone().ok_or(EtwError::Internal("No event channel".into()))?;
        let stats = self.stats.clone();
        let state_clone = self.state.clone();
        let stop_flag = Arc::new(AtomicBool::new(false));
        let stop_flag_clone = stop_flag.clone();

        // Build kernel trace
        // Note: KernelTrace API in ferrisetw uses builder pattern
        let trace_builder = KernelTrace::new();

        // Create callback
        let callback = move |record: &EventRecord, schema_locator: &SchemaLocator| {
            stats.record_event_received();

            // Parse event
            let event = crate::session::parse_event_record(record, schema_locator.event_schema(record).as_ref());

            // Send to channel
            match event_tx.try_send(event) {
                Ok(_) => {
                    stats.record_event_processed();
                }
                Err(TrySendError::Full(_)) => {
                    stats.record_events_lost(1);
                }
                Err(TrySendError::Disconnected(_)) => {}
            }
        };

        // Build trace with kernel provider
        let trace = trace_builder
            .enable(
                ferrisetw::provider::kernel::KernelProvider::new()
                    .add_callback(callback)
                    .build()
            )
            .build()
            .map_err(|e| EtwError::StartTraceFailed(format!("{:?}", e)))?;

        // Spawn processing thread
        let trace_thread = thread::spawn(move || {
            let _ = trace.start_and_process();
            *state_clone.write() = KernelSessionState::Stopped;
        });

        *self.state.write() = KernelSessionState::Running;
        self.handle = Some(KernelHandle {
            trace_thread: Some(trace_thread),
            stop_flag: stop_flag_clone,
        });

        Ok(())
    }

    /// Stop the kernel trace session
    pub fn stop(&mut self) -> Result<()> {
        let state = *self.state.read();
        if state != KernelSessionState::Running {
            return Err(EtwError::SessionNotRunning);
        }

        // Stop the trace
        stop_trace_by_name("NT Kernel Logger")
            .or_else(|_| stop_trace_by_name(&self.config.name))
            .map_err(|e| EtwError::StopTraceFailed(format!("{:?}", e)))?;

        // Set stop flag
        if let Some(ref handle) = self.handle {
            handle.stop_flag.store(true, Ordering::SeqCst);
        }

        *self.state.write() = KernelSessionState::Stopped;

        // Wait for thread to finish
        if let Some(mut handle) = self.handle.take() {
            if let Some(thread) = handle.trace_thread.take() {
                let _ = thread.join();
            }
        }

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
    pub fn stats(&self) -> crate::stats::SessionStats {
        self.stats.snapshot()
    }

    /// Check if session is running
    pub fn is_running(&self) -> bool {
        *self.state.read() == KernelSessionState::Running
    }
}

impl Default for KernelSession {
    fn default() -> Self {
        Self::new()
    }
}

impl Drop for KernelSession {
    fn drop(&mut self) {
        if self.is_running() {
            let _ = self.stop();
        }
    }
}

/// Python wrapper for KernelSession
#[pyclass(name = "KernelSession")]
pub struct PyKernelSession {
    inner: Option<KernelSession>,
}

#[pymethods]
impl PyKernelSession {
    /// Create a new kernel session
    #[new]
    fn new() -> Self {
        Self {
            inner: Some(KernelSession::new()),
        }
    }

    /// Enable process events
    fn enable_process(&mut self) -> PyResult<()> {
        if let Some(ref mut session) = self.inner {
            session.enable_category(KernelEventCategory::Process);
        }
        Ok(())
    }

    /// Enable thread events
    fn enable_thread(&mut self) -> PyResult<()> {
        if let Some(ref mut session) = self.inner {
            session.enable_category(KernelEventCategory::Thread);
        }
        Ok(())
    }

    /// Enable image load events
    fn enable_image_load(&mut self) -> PyResult<()> {
        if let Some(ref mut session) = self.inner {
            session.enable_category(KernelEventCategory::ImageLoad);
        }
        Ok(())
    }

    /// Enable network events
    fn enable_network(&mut self) -> PyResult<()> {
        if let Some(ref mut session) = self.inner {
            session.enable_category(KernelEventCategory::Network);
        }
        Ok(())
    }

    /// Enable file I/O events
    fn enable_file_io(&mut self) -> PyResult<()> {
        if let Some(ref mut session) = self.inner {
            session.enable_category(KernelEventCategory::FileIo);
        }
        Ok(())
    }

    /// Enable registry events
    fn enable_registry(&mut self) -> PyResult<()> {
        if let Some(ref mut session) = self.inner {
            session.enable_category(KernelEventCategory::Registry);
        }
        Ok(())
    }

    /// Enable all basic events (process, thread, image load)
    fn enable_all_basic(&mut self) -> PyResult<()> {
        if let Some(ref mut session) = self.inner {
            session.enable_category(KernelEventCategory::AllBasic);
        }
        Ok(())
    }

    /// Set event categories from flags
    fn set_categories(&mut self, flags: u32) -> PyResult<()> {
        if let Some(ref mut session) = self.inner {
            session.set_categories(flags);
        }
        Ok(())
    }

    /// Start the session
    fn start(&mut self) -> PyResult<()> {
        let session = self.inner.as_mut()
            .ok_or_else(|| pyo3::exceptions::PyRuntimeError::new_err("Session is closed"))?;
        session.start()?;
        Ok(())
    }

    /// Stop the session
    fn stop(&mut self) -> PyResult<()> {
        let session = self.inner.as_mut()
            .ok_or_else(|| pyo3::exceptions::PyRuntimeError::new_err("Session is closed"))?;
        session.stop()?;
        Ok(())
    }

    /// Get the next event (blocking)
    fn next_event(&self) -> PyResult<Option<crate::event::PyEtwEvent>> {
        let session = self.inner.as_ref()
            .ok_or_else(|| pyo3::exceptions::PyRuntimeError::new_err("Session is closed"))?;
        Ok(session.next_event().map(crate::event::PyEtwEvent::from))
    }

    /// Get the next event with timeout (in milliseconds)
    fn next_event_timeout(&self, timeout_ms: u64) -> PyResult<Option<crate::event::PyEtwEvent>> {
        let session = self.inner.as_ref()
            .ok_or_else(|| pyo3::exceptions::PyRuntimeError::new_err("Session is closed"))?;
        Ok(session
            .next_event_timeout(Duration::from_millis(timeout_ms))
            .map(crate::event::PyEtwEvent::from))
    }

    /// Get session statistics
    fn stats(&self) -> PyResult<crate::stats::PySessionStats> {
        let session = self.inner.as_ref()
            .ok_or_else(|| pyo3::exceptions::PyRuntimeError::new_err("Session is closed"))?;
        Ok(crate::stats::PySessionStats::from(session.stats()))
    }

    /// Check if session is running
    fn is_running(&self) -> bool {
        self.inner.as_ref().map(|s| s.is_running()).unwrap_or(false)
    }

    fn __repr__(&self) -> String {
        match &self.inner {
            Some(session) => format!(
                "KernelSession(running={})",
                session.is_running()
            ),
            None => "KernelSession(closed)".to_string(),
        }
    }
}

/// Python constants for kernel event categories
#[pyclass(name = "KernelFlags")]
pub struct PyKernelFlags;

#[pymethods]
impl PyKernelFlags {
    #[classattr]
    const PROCESS: u32 = KernelEventCategory::Process as u32;

    #[classattr]
    const THREAD: u32 = KernelEventCategory::Thread as u32;

    #[classattr]
    const IMAGE_LOAD: u32 = KernelEventCategory::ImageLoad as u32;

    #[classattr]
    const DISK_IO: u32 = KernelEventCategory::DiskIo as u32;

    #[classattr]
    const NETWORK: u32 = KernelEventCategory::Network as u32;

    #[classattr]
    const REGISTRY: u32 = KernelEventCategory::Registry as u32;

    #[classattr]
    const FILE_IO: u32 = KernelEventCategory::FileIo as u32;

    #[classattr]
    const ALL_BASIC: u32 = KernelEventCategory::AllBasic as u32;

    #[classattr]
    const ALL: u32 = KernelEventCategory::All as u32;
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_kernel_category_flags() {
        assert_eq!(KernelEventCategory::Process.to_flags(), 0x00000001);
        assert_eq!(KernelEventCategory::Thread.to_flags(), 0x00000002);
        assert_eq!(KernelEventCategory::ImageLoad.to_flags(), 0x00000004);
    }

    #[test]
    fn test_combine_categories() {
        let combined = KernelEventCategory::combine(&[
            KernelEventCategory::Process,
            KernelEventCategory::Thread,
        ]);
        assert_eq!(combined, 0x00000003);
    }

    #[test]
    fn test_kernel_session_creation() {
        let session = KernelSession::new();
        assert!(!session.is_running());
    }

    #[test]
    fn test_kernel_config_default() {
        let config = KernelSessionConfig::default();
        assert_eq!(config.name, "PyETWkit-Kernel");
        assert_eq!(config.categories, KernelEventCategory::AllBasic as u32);
    }
}
