//! PyETWkit Core - High-performance ETW consumer library
//!
//! This crate provides the Rust backend for PyETWkit, offering:
//! - ETW session management (UserTrace, KernelTrace)
//! - Event parsing and schema resolution
//! - Provider management and filtering
//! - Provider discovery and enumeration
//! - Python bindings via pyo3

// pyo3 macros generate code that triggers this clippy lint for PyResult<T> returns
// when impl From<CustomError> for PyErr is defined. This is a known issue with
// pyo3's generated code and not a real problem in our code.
// See: https://github.com/PyO3/pyo3/issues/3370
#![allow(clippy::useless_conversion)]

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
pub mod tdh;

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
fn _core(m: &Bound<'_, PyModule>) -> PyResult<()> {
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

    // Property formatting toggle
    m.add(
        "set_property_formatting",
        wrap_pyfunction!(tdh::py_set_property_formatting, m)?,
    )?;
    m.add(
        "property_formatting",
        wrap_pyfunction!(tdh::py_property_formatting, m)?,
    )?;

    // WPP decoding needs a directory of .tmf files to consult
    m.add(
        "set_wpp_tmf_search_path",
        wrap_pyfunction!(tdh::py_set_wpp_tmf_search_path, m)?,
    )?;
    m.add(
        "wpp_tmf_search_path",
        wrap_pyfunction!(tdh::py_wpp_tmf_search_path, m)?,
    )?;
    m.add(
        "set_wpp_tmf_file",
        wrap_pyfunction!(tdh::py_set_wpp_tmf_file, m)?,
    )?;
    m.add("wpp_tmf_file", wrap_pyfunction!(tdh::py_wpp_tmf_file, m)?)?;
    m.add(
        "set_wpp_pdb_path",
        wrap_pyfunction!(tdh::py_set_wpp_pdb_path, m)?,
    )?;
    m.add("wpp_pdb_path", wrap_pyfunction!(tdh::py_wpp_pdb_path, m)?)?;

    // Register ETL reader
    m.add_class::<etl_reader::PyEtlReader>()?;

    // Register EnableProperty enum
    m.add_class::<provider::PyEnableProperty>()?;

    // Register schema classes
    m.add_class::<schema::PyEventSchema>()?;
    m.add_class::<schema::PyPropertyInfo>()?;
    m.add_class::<schema::PySchemaCache>()?;

    // Register submodules
    let raw_module = PyModule::new(m.py(), "raw")?;
    session::register_raw_api(&raw_module)?;
    m.add_submodule(&raw_module)?;

    Ok(())
}
