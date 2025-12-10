//! Error types for PyETWkit

use pyo3::exceptions::{PyOSError, PyRuntimeError, PyValueError};
use pyo3::prelude::*;
use thiserror::Error;

/// Result type alias for PyETWkit operations
pub type Result<T> = std::result::Result<T, EtwError>;

/// ETW-related errors
#[derive(Error, Debug)]
pub enum EtwError {
    /// Session already exists with the given name
    #[error("ETW session '{0}' already exists")]
    SessionExists(String),

    /// Session not found
    #[error("ETW session '{0}' not found")]
    SessionNotFound(String),

    /// Failed to start trace
    #[error("Failed to start ETW trace: {0}")]
    StartTraceFailed(String),

    /// Failed to stop trace
    #[error("Failed to stop ETW trace: {0}")]
    StopTraceFailed(String),

    /// Failed to enable provider
    #[error("Failed to enable provider {0}: {1}")]
    EnableProviderFailed(String, String),

    /// Invalid provider GUID
    #[error("Invalid provider GUID: {0}")]
    InvalidProviderGuid(String),

    /// Provider not found
    #[error("Provider '{0}' not found")]
    ProviderNotFound(String),

    /// Event parsing error
    #[error("Failed to parse event: {0}")]
    EventParseError(String),

    /// Schema not found for event
    #[error("Schema not found for event (provider: {0}, id: {1})")]
    SchemaNotFound(String, u16),

    /// Permission denied (requires admin)
    #[error("Permission denied: ETW operations require administrator privileges")]
    PermissionDenied,

    /// Windows API error
    #[error("Windows API error: {0} (code: {1})")]
    WindowsError(String, u32),

    /// Channel error (for async operations)
    #[error("Channel error: {0}")]
    ChannelError(String),

    /// Timeout error
    #[error("Operation timed out after {0}ms")]
    Timeout(u64),

    /// Session is not running
    #[error("Session is not running")]
    SessionNotRunning,

    /// Session is already running
    #[error("Session is already running")]
    SessionAlreadyRunning,

    /// Invalid configuration
    #[error("Invalid configuration: {0}")]
    InvalidConfig(String),

    /// Buffer overflow - events lost
    #[error("Buffer overflow: {0} events lost")]
    BufferOverflow(u64),

    /// Internal error
    #[error("Internal error: {0}")]
    Internal(String),
}

impl From<EtwError> for PyErr {
    fn from(err: EtwError) -> PyErr {
        match &err {
            EtwError::PermissionDenied => PyOSError::new_err(err.to_string()),
            EtwError::InvalidProviderGuid(_) | EtwError::InvalidConfig(_) => {
                PyValueError::new_err(err.to_string())
            }
            EtwError::WindowsError(_, code) => {
                PyOSError::new_err(format!("{} (error code: {})", err, code))
            }
            _ => PyRuntimeError::new_err(err.to_string()),
        }
    }
}

impl From<std::io::Error> for EtwError {
    fn from(err: std::io::Error) -> Self {
        EtwError::Internal(err.to_string())
    }
}

impl<T> From<crossbeam_channel::SendError<T>> for EtwError {
    fn from(err: crossbeam_channel::SendError<T>) -> Self {
        EtwError::ChannelError(err.to_string())
    }
}

impl<T> From<crossbeam_channel::TrySendError<T>> for EtwError {
    fn from(err: crossbeam_channel::TrySendError<T>) -> Self {
        EtwError::ChannelError(err.to_string())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_error_display() {
        let err = EtwError::SessionExists("test".to_string());
        assert_eq!(err.to_string(), "ETW session 'test' already exists");
    }

    #[test]
    fn test_error_conversion_to_pyerr() {
        let err = EtwError::PermissionDenied;
        let py_err: PyErr = err.into();
        assert!(py_err.is_instance_of::<PyOSError>(pyo3::Python::with_gil(|py| py)));
    }
}
