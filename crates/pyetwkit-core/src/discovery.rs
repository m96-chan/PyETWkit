//! Provider discovery using TDH (Trace Data Helper) APIs
//!
//! This module provides functionality to enumerate and search ETW providers
//! installed on the system using Windows TDH APIs.

use crate::error::{EtwError, Result};
use pyo3::prelude::*;
use std::collections::HashMap;
use std::ffi::OsString;
use std::os::windows::ffi::OsStringExt;
use uuid::Uuid;
use windows::core::GUID;
use windows::Win32::System::Diagnostics::Etw::{
    TdhEnumerateProviders, PROVIDER_ENUMERATION_INFO, TRACE_PROVIDER_INFO,
};

/// Information about an ETW provider
#[derive(Debug, Clone)]
pub struct ProviderInfo {
    /// Provider GUID
    pub guid: Uuid,
    /// Provider name
    pub name: String,
    /// Source (manifest, MOF, etc.)
    pub source: ProviderSource,
}

/// Source of provider registration
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ProviderSource {
    /// XML manifest-based provider
    Xml,
    /// MOF-based provider (legacy)
    Mof,
    /// Unknown source
    Unknown,
}

/// Detailed provider information including keywords and events
#[derive(Debug, Clone)]
pub struct ProviderDetails {
    /// Basic provider info
    pub info: ProviderInfo,
    /// Available keywords (name -> value)
    pub keywords: HashMap<String, u64>,
}

/// List all ETW providers registered on the system
pub fn list_providers() -> Result<Vec<ProviderInfo>> {
    const ERROR_INSUFFICIENT_BUFFER: u32 = 122;

    unsafe {
        // First call to get required buffer size
        let mut buffer_size: u32 = 0;
        let result = TdhEnumerateProviders(None, &mut buffer_size);

        // ERROR_INSUFFICIENT_BUFFER is expected
        if result != 0 && result != ERROR_INSUFFICIENT_BUFFER {
            return Err(EtwError::TdhError(format!(
                "TdhEnumerateProviders failed: {}",
                result
            )));
        }

        if buffer_size == 0 {
            return Ok(Vec::new());
        }

        // Allocate buffer
        let mut buffer: Vec<u8> = vec![0u8; buffer_size as usize];
        let enum_info = buffer.as_mut_ptr() as *mut PROVIDER_ENUMERATION_INFO;

        // Second call to get actual data
        let result = TdhEnumerateProviders(Some(enum_info), &mut buffer_size);

        if result != 0 {
            return Err(EtwError::TdhError(format!(
                "TdhEnumerateProviders failed: {}",
                result
            )));
        }

        let enum_info_ref = &*enum_info;
        let provider_count = enum_info_ref.NumberOfProviders as usize;
        let mut providers = Vec::with_capacity(provider_count);

        // Get pointer to provider info array
        let provider_array_ptr = (enum_info as *const u8).add(std::mem::offset_of!(
            PROVIDER_ENUMERATION_INFO,
            TraceProviderInfoArray
        )) as *const TRACE_PROVIDER_INFO;

        for i in 0..provider_count {
            let provider_info = &*provider_array_ptr.add(i);

            // Convert GUID to Uuid
            let guid = guid_to_uuid(provider_info.ProviderGuid);

            // Get provider name from offset
            let name = if provider_info.ProviderNameOffset > 0 {
                let name_ptr = (enum_info as *const u8)
                    .add(provider_info.ProviderNameOffset as usize)
                    as *const u16;
                read_wide_string(name_ptr)
            } else {
                guid.to_string()
            };

            // Determine source type
            let source = match provider_info.SchemaSource {
                0 => ProviderSource::Xml,
                1 => ProviderSource::Mof,
                _ => ProviderSource::Unknown,
            };

            providers.push(ProviderInfo { guid, name, source });
        }

        Ok(providers)
    }
}

/// Search providers by keyword (case-insensitive partial match)
pub fn search_providers(keyword: &str) -> Result<Vec<ProviderInfo>> {
    let all_providers = list_providers()?;
    let keyword_lower = keyword.to_lowercase();

    let matches: Vec<ProviderInfo> = all_providers
        .into_iter()
        .filter(|p| p.name.to_lowercase().contains(&keyword_lower))
        .collect();

    Ok(matches)
}

/// Get detailed information about a specific provider
pub fn get_provider_info(name_or_guid: &str) -> Result<Option<ProviderDetails>> {
    let all_providers = list_providers()?;

    // Try to find by name or GUID
    let provider = if let Ok(guid) = Uuid::parse_str(name_or_guid) {
        all_providers.into_iter().find(|p| p.guid == guid)
    } else {
        all_providers
            .into_iter()
            .find(|p| p.name.eq_ignore_ascii_case(name_or_guid))
    };

    match provider {
        Some(info) => {
            // Get keywords for this provider
            let keywords = get_provider_keywords(&info.guid).unwrap_or_default();
            Ok(Some(ProviderDetails { info, keywords }))
        }
        None => Ok(None),
    }
}

/// Get keywords for a specific provider
fn get_provider_keywords(_guid: &Uuid) -> Result<HashMap<String, u64>> {
    // TdhGetProviderFieldInformation can be used to get keywords
    // For now, return empty - this is a placeholder for full implementation
    Ok(HashMap::new())
}

/// Convert Windows GUID to uuid::Uuid
fn guid_to_uuid(guid: GUID) -> Uuid {
    Uuid::from_fields(guid.data1, guid.data2, guid.data3, &guid.data4)
}

/// Read a null-terminated wide string from a pointer
unsafe fn read_wide_string(ptr: *const u16) -> String {
    if ptr.is_null() {
        return String::new();
    }

    let mut len = 0;
    while *ptr.add(len) != 0 {
        len += 1;
    }

    let slice = std::slice::from_raw_parts(ptr, len);
    OsString::from_wide(slice).to_string_lossy().into_owned()
}

// Python bindings

/// Python wrapper for ProviderInfo
#[pyclass(name = "ProviderInfo")]
#[derive(Clone)]
pub struct PyProviderInfo {
    inner: ProviderInfo,
}

#[pymethods]
impl PyProviderInfo {
    /// Get provider GUID as string
    #[getter]
    fn guid(&self) -> String {
        self.inner.guid.to_string()
    }

    /// Get provider name
    #[getter]
    fn name(&self) -> &str {
        &self.inner.name
    }

    /// Get provider source type
    #[getter]
    fn source(&self) -> &str {
        match self.inner.source {
            ProviderSource::Xml => "xml",
            ProviderSource::Mof => "mof",
            ProviderSource::Unknown => "unknown",
        }
    }

    fn __repr__(&self) -> String {
        format!(
            "ProviderInfo(name='{}', guid='{}')",
            self.inner.name, self.inner.guid
        )
    }
}

impl From<ProviderInfo> for PyProviderInfo {
    fn from(info: ProviderInfo) -> Self {
        Self { inner: info }
    }
}

/// Python wrapper for ProviderDetails
#[pyclass(name = "ProviderDetails")]
#[derive(Clone)]
pub struct PyProviderDetails {
    inner: ProviderDetails,
}

#[pymethods]
impl PyProviderDetails {
    /// Get provider GUID as string
    #[getter]
    fn guid(&self) -> String {
        self.inner.info.guid.to_string()
    }

    /// Get provider name
    #[getter]
    fn name(&self) -> &str {
        &self.inner.info.name
    }

    /// Get keywords as dict
    #[getter]
    fn keywords(&self) -> HashMap<String, u64> {
        self.inner.keywords.clone()
    }

    fn __repr__(&self) -> String {
        format!(
            "ProviderDetails(name='{}', keywords={})",
            self.inner.info.name,
            self.inner.keywords.len()
        )
    }
}

impl From<ProviderDetails> for PyProviderDetails {
    fn from(details: ProviderDetails) -> Self {
        Self { inner: details }
    }
}

/// List all ETW providers on the system
#[pyfunction]
pub fn py_list_providers() -> PyResult<Vec<PyProviderInfo>> {
    list_providers()
        .map(|providers| providers.into_iter().map(PyProviderInfo::from).collect())
        .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))
}

/// Search providers by keyword
#[pyfunction]
pub fn py_search_providers(keyword: &str) -> PyResult<Vec<PyProviderInfo>> {
    search_providers(keyword)
        .map(|providers| providers.into_iter().map(PyProviderInfo::from).collect())
        .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))
}

/// Get detailed info for a specific provider
#[pyfunction]
pub fn py_get_provider_info(name_or_guid: &str) -> PyResult<Option<PyProviderDetails>> {
    get_provider_info(name_or_guid)
        .map(|opt| opt.map(PyProviderDetails::from))
        .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_list_providers() {
        let providers = list_providers().unwrap();
        assert!(!providers.is_empty());
    }

    #[test]
    fn test_search_providers() {
        let results = search_providers("Kernel").unwrap();
        // Should find at least one kernel provider
        assert!(!results.is_empty());
    }
}
