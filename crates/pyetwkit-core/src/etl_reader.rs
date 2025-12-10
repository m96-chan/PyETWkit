//! ETL (Event Trace Log) file reading functionality
//!
//! This module provides the ability to read events from ETL files
//! created by Windows Performance Recorder or other ETW logging tools.

use crate::error::{EtwError, Result};
use crate::event::EtwEvent;
use crate::session::parse_event_record;

use ferrisetw::schema_locator::SchemaLocator;
use ferrisetw::trace::FileTrace;
use ferrisetw::EventRecord;
use pyo3::prelude::*;
use std::path::{Path, PathBuf};
use std::sync::mpsc::{channel, Receiver};
use std::thread::{self, JoinHandle};

/// ETL file reader for reading events from trace log files
pub struct EtlReader {
    /// Path to the ETL file
    path: String,
    /// Event receiver
    receiver: Option<Receiver<EtwEvent>>,
    /// Processing thread handle
    thread_handle: Option<JoinHandle<()>>,
}

impl EtlReader {
    /// Create a new ETL reader for the specified file
    pub fn new<P: AsRef<Path>>(path: P) -> Result<Self> {
        let path_str = path.as_ref().to_string_lossy().to_string();

        // Verify file exists
        if !path.as_ref().exists() {
            return Err(EtwError::FileNotFound(path_str));
        }

        Ok(Self {
            path: path_str,
            receiver: None,
            thread_handle: None,
        })
    }

    /// Start reading events from the file
    pub fn start(&mut self) -> Result<()> {
        let (tx, rx) = channel();
        self.receiver = Some(rx);

        let path = PathBuf::from(&self.path);

        // Spawn thread to process file
        let handle = thread::spawn(move || {
            let callback = move |record: &EventRecord, locator: &SchemaLocator| {
                let schema = locator.event_schema(record).ok();
                let event = parse_event_record(record, schema.as_ref().map(|s| s.as_ref()));
                let _ = tx.send(event);
            };

            // Build file trace using ferrisetw
            // FileTrace::new returns a builder, then call start_and_process to begin
            let trace_builder = FileTrace::new(path, callback);

            // Process all events - this blocks until file is fully read
            let _ = trace_builder.start_and_process();
        });

        self.thread_handle = Some(handle);
        Ok(())
    }

    /// Get the next event from the file
    pub fn next_event(&mut self) -> Option<EtwEvent> {
        self.receiver.as_ref()?.recv().ok()
    }

    /// Try to get the next event without blocking
    pub fn try_next_event(&mut self) -> Option<EtwEvent> {
        self.receiver.as_ref()?.try_recv().ok()
    }

    /// Check if reading is complete
    pub fn is_finished(&self) -> bool {
        if let Some(handle) = &self.thread_handle {
            handle.is_finished()
        } else {
            true
        }
    }

    /// Wait for reading to complete
    pub fn wait(&mut self) {
        if let Some(handle) = self.thread_handle.take() {
            let _ = handle.join();
        }
    }

    /// Get file path
    pub fn path(&self) -> &str {
        &self.path
    }
}

impl Iterator for EtlReader {
    type Item = EtwEvent;

    fn next(&mut self) -> Option<Self::Item> {
        // Start if not already started
        if self.receiver.is_none() {
            if self.start().is_err() {
                return None;
            }
        }
        self.next_event()
    }
}

/// Python wrapper for EtlReader
#[pyclass(name = "EtlReader")]
pub struct PyEtlReader {
    inner: Option<EtlReader>,
    started: bool,
}

#[pymethods]
impl PyEtlReader {
    /// Create a new ETL reader
    #[new]
    fn new(path: &str) -> PyResult<Self> {
        let reader = EtlReader::new(path)
            .map_err(|e| pyo3::exceptions::PyFileNotFoundError::new_err(e.to_string()))?;
        Ok(Self {
            inner: Some(reader),
            started: false,
        })
    }

    /// Get the file path
    #[getter]
    fn path(&self) -> PyResult<&str> {
        self.inner
            .as_ref()
            .map(|r| r.path())
            .ok_or_else(|| pyo3::exceptions::PyRuntimeError::new_err("Reader is closed"))
    }

    /// Check if reading is finished
    fn is_finished(&self) -> bool {
        self.inner.as_ref().map(|r| r.is_finished()).unwrap_or(true)
    }

    /// Read all events as a list
    fn read_all(&mut self) -> PyResult<Vec<crate::event::PyEtwEvent>> {
        let reader = self
            .inner
            .as_mut()
            .ok_or_else(|| pyo3::exceptions::PyRuntimeError::new_err("Reader is closed"))?;

        if !self.started {
            reader
                .start()
                .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
            self.started = true;
        }

        let mut events = Vec::new();
        while let Some(event) = reader.next_event() {
            events.push(crate::event::PyEtwEvent::from(event));
        }
        reader.wait();

        Ok(events)
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
    ) -> bool {
        if let Some(mut reader) = self.inner.take() {
            reader.wait();
        }
        false
    }

    /// Iterator protocol
    fn __iter__(slf: PyRef<'_, Self>) -> PyRef<'_, Self> {
        slf
    }

    /// Get next event
    fn __next__(&mut self) -> PyResult<Option<crate::event::PyEtwEvent>> {
        let reader = self
            .inner
            .as_mut()
            .ok_or_else(|| pyo3::exceptions::PyRuntimeError::new_err("Reader is closed"))?;

        if !self.started {
            reader
                .start()
                .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
            self.started = true;
        }

        Ok(reader.try_next_event().map(crate::event::PyEtwEvent::from))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_etl_reader_file_not_found() {
        let result = EtlReader::new("nonexistent.etl");
        assert!(result.is_err());
    }
}
