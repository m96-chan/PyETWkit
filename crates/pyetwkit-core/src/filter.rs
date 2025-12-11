//! Event filtering

use pyo3::prelude::*;
use serde::{Deserialize, Serialize};
use std::sync::Arc;

/// Event filter types
#[derive(Serialize, Deserialize)]
pub enum EventFilter {
    /// Filter by specific event IDs
    EventIds(Vec<u16>),
    /// Filter by opcode
    Opcodes(Vec<u8>),
    /// Filter by process ID
    ProcessId(u32),
    /// Filter by process name (substring match)
    ProcessName(String),
    /// Exclude specific event IDs
    ExcludeEventIds(Vec<u16>),
    /// Custom predicate (not serializable, uses Arc for Clone)
    #[serde(skip)]
    Custom(Arc<dyn Fn(u16, u8) -> bool + Send + Sync>),
}

impl Clone for EventFilter {
    fn clone(&self) -> Self {
        match self {
            Self::EventIds(v) => Self::EventIds(v.clone()),
            Self::Opcodes(v) => Self::Opcodes(v.clone()),
            Self::ProcessId(v) => Self::ProcessId(*v),
            Self::ProcessName(v) => Self::ProcessName(v.clone()),
            Self::ExcludeEventIds(v) => Self::ExcludeEventIds(v.clone()),
            Self::Custom(f) => Self::Custom(Arc::clone(f)),
        }
    }
}

impl std::fmt::Debug for EventFilter {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::EventIds(v) => f.debug_tuple("EventIds").field(v).finish(),
            Self::Opcodes(v) => f.debug_tuple("Opcodes").field(v).finish(),
            Self::ProcessId(v) => f.debug_tuple("ProcessId").field(v).finish(),
            Self::ProcessName(v) => f.debug_tuple("ProcessName").field(v).finish(),
            Self::ExcludeEventIds(v) => f.debug_tuple("ExcludeEventIds").field(v).finish(),
            Self::Custom(_) => f.debug_tuple("Custom").field(&"<fn>").finish(),
        }
    }
}

impl EventFilter {
    /// Check if the filter matches the given event
    pub fn matches(&self, event_id: u16, opcode: u8) -> bool {
        match self {
            EventFilter::EventIds(ids) => ids.contains(&event_id),
            EventFilter::Opcodes(ops) => ops.contains(&opcode),
            EventFilter::ExcludeEventIds(ids) => !ids.contains(&event_id),
            EventFilter::Custom(f) => f(event_id, opcode),
            // These need additional context, return true for now
            EventFilter::ProcessId(_) | EventFilter::ProcessName(_) => true,
        }
    }

    /// Check if this filter matches a process
    pub fn matches_process(&self, pid: u32, process_name: Option<&str>) -> bool {
        match self {
            EventFilter::ProcessId(filter_pid) => *filter_pid == pid,
            EventFilter::ProcessName(name) => {
                process_name.is_some_and(|pn| pn.to_lowercase().contains(&name.to_lowercase()))
            }
            _ => true,
        }
    }
}

/// Filter builder for chaining multiple filters
#[derive(Debug, Clone, Default)]
pub struct FilterBuilder {
    filters: Vec<EventFilter>,
}

impl FilterBuilder {
    /// Create a new filter builder
    pub fn new() -> Self {
        Self::default()
    }

    /// Filter by specific event IDs
    pub fn event_ids(mut self, ids: impl IntoIterator<Item = u16>) -> Self {
        self.filters
            .push(EventFilter::EventIds(ids.into_iter().collect()));
        self
    }

    /// Filter by opcodes
    pub fn opcodes(mut self, opcodes: impl IntoIterator<Item = u8>) -> Self {
        self.filters
            .push(EventFilter::Opcodes(opcodes.into_iter().collect()));
        self
    }

    /// Filter by process ID
    pub fn process_id(mut self, pid: u32) -> Self {
        self.filters.push(EventFilter::ProcessId(pid));
        self
    }

    /// Filter by process name
    pub fn process_name(mut self, name: impl Into<String>) -> Self {
        self.filters.push(EventFilter::ProcessName(name.into()));
        self
    }

    /// Exclude specific event IDs
    pub fn exclude_event_ids(mut self, ids: impl IntoIterator<Item = u16>) -> Self {
        self.filters
            .push(EventFilter::ExcludeEventIds(ids.into_iter().collect()));
        self
    }

    /// Build the filters
    pub fn build(self) -> Vec<EventFilter> {
        self.filters
    }

    /// Check if all filters match
    pub fn matches_all(
        &self,
        event_id: u16,
        opcode: u8,
        pid: u32,
        process_name: Option<&str>,
    ) -> bool {
        for filter in &self.filters {
            if !filter.matches(event_id, opcode) {
                return false;
            }
            if !filter.matches_process(pid, process_name) {
                return false;
            }
        }
        true
    }
}

/// Python wrapper for event filtering
#[pyclass(name = "EventFilter")]
#[derive(Clone)]
pub struct PyEventFilter {
    pub(crate) filters: Vec<EventFilter>,
}

#[pymethods]
impl PyEventFilter {
    /// Create a new empty filter
    #[new]
    fn new() -> Self {
        Self {
            filters: Vec::new(),
        }
    }

    /// Filter by specific event IDs
    fn event_ids(&mut self, ids: Vec<u16>) -> Self {
        self.filters.push(EventFilter::EventIds(ids));
        self.clone()
    }

    /// Filter by opcodes
    fn opcodes(&mut self, opcodes: Vec<u8>) -> Self {
        self.filters.push(EventFilter::Opcodes(opcodes));
        self.clone()
    }

    /// Filter by process ID
    fn process_id(&mut self, pid: u32) -> Self {
        self.filters.push(EventFilter::ProcessId(pid));
        self.clone()
    }

    /// Filter by process name (substring match)
    fn process_name(&mut self, name: String) -> Self {
        self.filters.push(EventFilter::ProcessName(name));
        self.clone()
    }

    /// Exclude specific event IDs
    fn exclude_event_ids(&mut self, ids: Vec<u16>) -> Self {
        self.filters.push(EventFilter::ExcludeEventIds(ids));
        self.clone()
    }

    /// Check if the filter matches the given event
    fn matches(&self, event_id: u16, opcode: u8) -> bool {
        for filter in &self.filters {
            if !filter.matches(event_id, opcode) {
                return false;
            }
        }
        true
    }

    fn __repr__(&self) -> String {
        format!("EventFilter(count={})", self.filters.len())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_event_id_filter() {
        let filter = EventFilter::EventIds(vec![1, 2, 3]);
        assert!(filter.matches(1, 0));
        assert!(filter.matches(2, 0));
        assert!(!filter.matches(4, 0));
    }

    #[test]
    fn test_opcode_filter() {
        let filter = EventFilter::Opcodes(vec![10, 20]);
        assert!(filter.matches(1, 10));
        assert!(filter.matches(1, 20));
        assert!(!filter.matches(1, 30));
    }

    #[test]
    fn test_exclude_filter() {
        let filter = EventFilter::ExcludeEventIds(vec![100, 200]);
        assert!(filter.matches(1, 0));
        assert!(!filter.matches(100, 0));
        assert!(!filter.matches(200, 0));
    }

    #[test]
    fn test_process_filter() {
        let filter = EventFilter::ProcessId(1234);
        assert!(filter.matches_process(1234, None));
        assert!(!filter.matches_process(5678, None));

        let filter = EventFilter::ProcessName("chrome".to_string());
        assert!(filter.matches_process(0, Some("chrome.exe")));
        assert!(filter.matches_process(0, Some("Google Chrome")));
        assert!(!filter.matches_process(0, Some("firefox.exe")));
    }

    #[test]
    fn test_filter_builder() {
        let filters = FilterBuilder::new()
            .event_ids([1, 2, 3])
            .process_id(1000)
            .build();

        assert_eq!(filters.len(), 2);
    }

    #[test]
    fn test_filter_builder_matches() {
        let builder = FilterBuilder::new().event_ids([1, 2, 3]).process_id(1000);

        assert!(builder.matches_all(1, 0, 1000, None));
        assert!(!builder.matches_all(4, 0, 1000, None)); // Wrong event ID
        assert!(!builder.matches_all(1, 0, 2000, None)); // Wrong PID
    }
}
