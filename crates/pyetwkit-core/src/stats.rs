//! Session statistics and monitoring

use pyo3::prelude::*;
use serde::{Deserialize, Serialize};
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::Arc;
use std::time::Instant;

/// Session statistics
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SessionStats {
    /// Number of events received
    pub events_received: u64,
    /// Number of events processed
    pub events_processed: u64,
    /// Number of events lost due to buffer overflow
    pub events_lost: u64,
    /// Number of buffers lost
    pub buffers_lost: u64,
    /// Number of buffers read
    pub buffers_read: u64,
    /// Current buffer size in KB
    pub buffer_size_kb: u32,
    /// Number of buffers allocated
    pub buffers_allocated: u32,
    /// Session start time (Unix timestamp)
    pub start_time: i64,
    /// Duration in seconds
    pub duration_secs: f64,
    /// Events per second
    pub events_per_second: f64,
}

impl Default for SessionStats {
    fn default() -> Self {
        Self {
            events_received: 0,
            events_processed: 0,
            events_lost: 0,
            buffers_lost: 0,
            buffers_read: 0,
            buffer_size_kb: 64,
            buffers_allocated: 0,
            start_time: 0,
            duration_secs: 0.0,
            events_per_second: 0.0,
        }
    }
}

/// Thread-safe statistics tracker
#[derive(Debug)]
pub struct StatsTracker {
    events_received: AtomicU64,
    events_processed: AtomicU64,
    events_lost: AtomicU64,
    buffers_lost: AtomicU64,
    buffers_read: AtomicU64,
    start_time: Instant,
    buffer_size_kb: u32,
    buffers_allocated: u32,
}

impl StatsTracker {
    /// Create a new stats tracker
    pub fn new(buffer_size_kb: u32, buffers_allocated: u32) -> Self {
        Self {
            events_received: AtomicU64::new(0),
            events_processed: AtomicU64::new(0),
            events_lost: AtomicU64::new(0),
            buffers_lost: AtomicU64::new(0),
            buffers_read: AtomicU64::new(0),
            start_time: Instant::now(),
            buffer_size_kb,
            buffers_allocated,
        }
    }

    /// Increment events received counter
    pub fn record_event_received(&self) {
        self.events_received.fetch_add(1, Ordering::Relaxed);
    }

    /// Increment events processed counter
    pub fn record_event_processed(&self) {
        self.events_processed.fetch_add(1, Ordering::Relaxed);
    }

    /// Record lost events
    pub fn record_events_lost(&self, count: u64) {
        self.events_lost.fetch_add(count, Ordering::Relaxed);
    }

    /// Record lost buffers
    pub fn record_buffers_lost(&self, count: u64) {
        self.buffers_lost.fetch_add(count, Ordering::Relaxed);
    }

    /// Increment buffers read counter
    pub fn record_buffer_read(&self) {
        self.buffers_read.fetch_add(1, Ordering::Relaxed);
    }

    /// Get current statistics snapshot
    pub fn snapshot(&self) -> SessionStats {
        let duration = self.start_time.elapsed();
        let events_received = self.events_received.load(Ordering::Relaxed);
        let events_processed = self.events_processed.load(Ordering::Relaxed);
        let duration_secs = duration.as_secs_f64();

        SessionStats {
            events_received,
            events_processed,
            events_lost: self.events_lost.load(Ordering::Relaxed),
            buffers_lost: self.buffers_lost.load(Ordering::Relaxed),
            buffers_read: self.buffers_read.load(Ordering::Relaxed),
            buffer_size_kb: self.buffer_size_kb,
            buffers_allocated: self.buffers_allocated,
            start_time: std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .map(|d| d.as_secs() as i64 - duration.as_secs() as i64)
                .unwrap_or(0),
            duration_secs,
            events_per_second: if duration_secs > 0.0 {
                events_processed as f64 / duration_secs
            } else {
                0.0
            },
        }
    }

    /// Reset all counters
    pub fn reset(&self) {
        self.events_received.store(0, Ordering::Relaxed);
        self.events_processed.store(0, Ordering::Relaxed);
        self.events_lost.store(0, Ordering::Relaxed);
        self.buffers_lost.store(0, Ordering::Relaxed);
        self.buffers_read.store(0, Ordering::Relaxed);
    }
}

impl Default for StatsTracker {
    fn default() -> Self {
        Self::new(64, 64)
    }
}

/// Shared stats tracker
pub type SharedStatsTracker = Arc<StatsTracker>;

/// Python wrapper for SessionStats
#[pyclass(name = "SessionStats")]
#[derive(Clone)]
pub struct PySessionStats {
    inner: SessionStats,
}

#[pymethods]
impl PySessionStats {
    /// Number of events received
    #[getter]
    fn events_received(&self) -> u64 {
        self.inner.events_received
    }

    /// Number of events processed
    #[getter]
    fn events_processed(&self) -> u64 {
        self.inner.events_processed
    }

    /// Number of events lost
    #[getter]
    fn events_lost(&self) -> u64 {
        self.inner.events_lost
    }

    /// Number of buffers lost
    #[getter]
    fn buffers_lost(&self) -> u64 {
        self.inner.buffers_lost
    }

    /// Number of buffers read
    #[getter]
    fn buffers_read(&self) -> u64 {
        self.inner.buffers_read
    }

    /// Buffer size in KB
    #[getter]
    fn buffer_size_kb(&self) -> u32 {
        self.inner.buffer_size_kb
    }

    /// Number of buffers allocated
    #[getter]
    fn buffers_allocated(&self) -> u32 {
        self.inner.buffers_allocated
    }

    /// Session duration in seconds
    #[getter]
    fn duration_secs(&self) -> f64 {
        self.inner.duration_secs
    }

    /// Events per second
    #[getter]
    fn events_per_second(&self) -> f64 {
        self.inner.events_per_second
    }

    /// Check if any events were lost
    fn has_loss(&self) -> bool {
        self.inner.events_lost > 0 || self.inner.buffers_lost > 0
    }

    /// Get loss percentage
    fn loss_percentage(&self) -> f64 {
        let total = self.inner.events_received + self.inner.events_lost;
        if total > 0 {
            (self.inner.events_lost as f64 / total as f64) * 100.0
        } else {
            0.0
        }
    }

    /// Convert to dictionary
    fn to_dict(&self, py: Python<'_>) -> PyResult<PyObject> {
        let dict = pyo3::types::PyDict::new(py);
        dict.set_item("events_received", self.inner.events_received)?;
        dict.set_item("events_processed", self.inner.events_processed)?;
        dict.set_item("events_lost", self.inner.events_lost)?;
        dict.set_item("buffers_lost", self.inner.buffers_lost)?;
        dict.set_item("buffers_read", self.inner.buffers_read)?;
        dict.set_item("buffer_size_kb", self.inner.buffer_size_kb)?;
        dict.set_item("buffers_allocated", self.inner.buffers_allocated)?;
        dict.set_item("duration_secs", self.inner.duration_secs)?;
        dict.set_item("events_per_second", self.inner.events_per_second)?;
        Ok(dict.into())
    }

    fn __repr__(&self) -> String {
        format!(
            "SessionStats(events={}, lost={}, eps={:.1})",
            self.inner.events_processed, self.inner.events_lost, self.inner.events_per_second
        )
    }
}

impl From<SessionStats> for PySessionStats {
    fn from(stats: SessionStats) -> Self {
        Self { inner: stats }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_stats_tracker() {
        let tracker = StatsTracker::new(64, 64);

        tracker.record_event_received();
        tracker.record_event_received();
        tracker.record_event_processed();
        tracker.record_events_lost(5);

        let stats = tracker.snapshot();
        assert_eq!(stats.events_received, 2);
        assert_eq!(stats.events_processed, 1);
        assert_eq!(stats.events_lost, 5);
    }

    #[test]
    fn test_stats_reset() {
        let tracker = StatsTracker::new(64, 64);

        tracker.record_event_received();
        tracker.record_events_lost(10);
        tracker.reset();

        let stats = tracker.snapshot();
        assert_eq!(stats.events_received, 0);
        assert_eq!(stats.events_lost, 0);
    }

    #[test]
    fn test_default_stats() {
        let stats = SessionStats::default();
        assert_eq!(stats.events_received, 0);
        assert_eq!(stats.buffer_size_kb, 64);
    }
}
