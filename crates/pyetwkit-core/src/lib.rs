//! PyETWkit Core - High-performance ETW consumer library
//!
//! This crate provides the Rust backend for PyETWkit, offering:
//! - ETW session management (UserTrace, KernelTrace)
//! - Event parsing and schema resolution
//! - Provider management and filtering
//! - Python bindings via pyo3

pub mod error;
pub mod event;
pub mod filter;
pub mod kernel;
pub mod provider;
pub mod session;
pub mod stats;

// Re-export main types
pub use error::{EtwError, Result};
pub use event::EtwEvent;
pub use filter::EventFilter;
pub use kernel::{KernelEventCategory, KernelSession, KernelSessionConfig};
pub use provider::EtwProvider;
pub use session::{EtwSession, SessionConfig, TraceMode};
pub use stats::SessionStats;

use pyo3::prelude::*;

/// PyETWkit Python module
#[pymodule]
fn pyetwkit_core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    // Register Python classes
    m.add_class::<event::PyEtwEvent>()?;
    m.add_class::<provider::PyEtwProvider>()?;
    m.add_class::<session::PyEtwSession>()?;
    m.add_class::<filter::PyEventFilter>()?;
    m.add_class::<stats::PySessionStats>()?;

    // Register kernel classes
    m.add_class::<kernel::PyKernelSession>()?;
    m.add_class::<kernel::PyKernelFlags>()?;

    // Register submodules
    let raw_module = PyModule::new_bound(m.py(), "raw")?;
    session::register_raw_api(&raw_module)?;
    m.add_submodule(&raw_module)?;

    Ok(())
}
