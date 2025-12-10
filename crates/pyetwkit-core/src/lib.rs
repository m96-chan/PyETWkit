//! PyETWkit Core - High-performance ETW consumer library
//!
//! This crate provides the Rust backend for PyETWkit, offering:
//! - ETW session management (UserTrace, KernelTrace)
//! - Event parsing and schema resolution
//! - Provider management and filtering
//! - Provider discovery and enumeration
//! - Python bindings via pyo3

pub mod discovery;
pub mod error;
pub mod etl_reader;
pub mod event;
pub mod filter;
pub mod kernel;
pub mod provider;
pub mod schema;
pub mod session;
pub mod stats;

// Re-export main types
pub use discovery::{
    get_provider_info, list_providers, search_providers, ProviderDetails, ProviderInfo,
};
pub use error::{EtwError, Result};
pub use etl_reader::EtlReader;
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

    // Register discovery classes and functions
    m.add_class::<discovery::PyProviderInfo>()?;
    m.add_class::<discovery::PyProviderDetails>()?;
    // Expose with Python-friendly names
    m.add(
        "list_providers",
        wrap_pyfunction!(discovery::py_list_providers, m)?,
    )?;
    m.add(
        "search_providers",
        wrap_pyfunction!(discovery::py_search_providers, m)?,
    )?;
    m.add(
        "get_provider_info",
        wrap_pyfunction!(discovery::py_get_provider_info, m)?,
    )?;

    // Register ETL reader
    m.add_class::<etl_reader::PyEtlReader>()?;

    // Register EnableProperty enum
    m.add_class::<provider::PyEnableProperty>()?;

    // Register schema classes
    m.add_class::<schema::PyEventSchema>()?;
    m.add_class::<schema::PyPropertyInfo>()?;
    m.add_class::<schema::PySchemaCache>()?;

    // Register submodules
    let raw_module = PyModule::new_bound(m.py(), "raw")?;
    session::register_raw_api(&raw_module)?;
    m.add_submodule(&raw_module)?;

    Ok(())
}
