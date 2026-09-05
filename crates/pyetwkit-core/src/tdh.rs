//! Generic event property parsing via TDH (Trace Data Helper)
//!
//! Before this module existed, [`crate::session::parse_event_record`] could only
//! recover properties whose names it guessed in advance, because ferrisetw keeps
//! `Schema::properties()` crate-private and so gives us no way to enumerate an
//! event's real schema. Anything not on the guess list was silently dropped,
//! which is why `EtwEvent.to_dict()` came back nearly empty for most providers.
//!
//! Here we go to TDH directly instead:
//!
//! 1. [`TdhGetEventInformation`] turns an `EVENT_RECORD` into a `TRACE_EVENT_INFO`
//!    describing every property, cached per (provider, event id, version).
//! 2. Property *names and types* are read out of that description.
//! 3. Each value is then fetched by name with [`TdhGetPropertySize`] and
//!    [`TdhGetProperty`].
//!
//! Step 3 is deliberate. The obvious implementation walks `EventPropertyInfo[]`
//! and computes offsets into the user data by hand, but property lengths and
//! counts may refer to *other* properties, so an arithmetic mistake there is
//! memory unsafety rather than a merely wrong value. Addressing properties by
//! name makes TDH compute those offsets for us, including past variable-length
//! properties. It costs an extra call per property; the schema cache keeps the
//! expensive half off the hot path.

use crate::event::EventValue;
use chrono::{TimeZone, Utc};
use ferrisetw::EventRecord;
use parking_lot::Mutex;
use std::collections::HashMap;
use std::sync::{Arc, OnceLock};
use uuid::Uuid;
use windows::Win32::System::Diagnostics::Etw::{
    TdhGetEventInformation, TdhGetProperty, TdhGetPropertySize, EVENT_PROPERTY_INFO, EVENT_RECORD,
    PROPERTY_DATA_DESCRIPTOR, TRACE_EVENT_INFO,
};

/// `EVENT_HEADER_FLAG_32_BIT_HEADER`, used to pick the pointer width of the
/// process that emitted the event rather than of this one.
const EVENT_HEADER_FLAG_32_BIT_HEADER: u16 = 0x0020;

const ERROR_SUCCESS: u32 = 0;
const ERROR_INSUFFICIENT_BUFFER: u32 = 122;

/// `PROPERTY_FLAGS` bit marking a property as a nested structure.
const PROPERTY_STRUCT: i32 = 1;

// TDH input types. Values from `_TDH_IN_TYPE`; matched numerically because the
// schema stores them as bare `u16`.
const IN_NULL: u16 = 0;
const IN_UNICODESTRING: u16 = 1;
const IN_ANSISTRING: u16 = 2;
const IN_INT8: u16 = 3;
const IN_UINT8: u16 = 4;
const IN_INT16: u16 = 5;
const IN_UINT16: u16 = 6;
const IN_INT32: u16 = 7;
const IN_UINT32: u16 = 8;
const IN_INT64: u16 = 9;
const IN_UINT64: u16 = 10;
const IN_FLOAT: u16 = 11;
const IN_DOUBLE: u16 = 12;
const IN_BOOLEAN: u16 = 13;
const IN_BINARY: u16 = 14;
const IN_GUID: u16 = 15;
const IN_POINTER: u16 = 16;
const IN_FILETIME: u16 = 17;
const IN_SYSTEMTIME: u16 = 18;
const IN_SID: u16 = 19;
const IN_HEXINT32: u16 = 20;
const IN_HEXINT64: u16 = 21;
const IN_COUNTEDSTRING: u16 = 300;
const IN_COUNTEDANSISTRING: u16 = 301;
const IN_NONNULLTERMINATEDSTRING: u16 = 304;
const IN_NONNULLTERMINATEDANSISTRING: u16 = 305;
const IN_UNICODECHAR: u16 = 306;
const IN_ANSICHAR: u16 = 307;
const IN_SIZET: u16 = 308;
const IN_HEXDUMP: u16 = 309;
const IN_MANIFEST_COUNTEDSTRING: u16 = 22;
const IN_MANIFEST_COUNTEDANSISTRING: u16 = 23;
const IN_MANIFEST_COUNTEDBINARY: u16 = 25;

/// One property's name and type, lifted out of `TRACE_EVENT_INFO` so that the
/// cached entry owns no pointers into the original buffer.
#[derive(Debug, Clone)]
struct PropertyDesc {
    name: String,
    /// `name` as a NUL-terminated UTF-16 string, kept ready for
    /// `PROPERTY_DATA_DESCRIPTOR::PropertyName`.
    name_utf16: Vec<u16>,
    in_type: u16,
    out_type: u16,
    is_struct: bool,
}

/// The parsed, owned form of a `TRACE_EVENT_INFO` for one event layout.
#[derive(Debug, Clone, Default)]
struct EventLayout {
    properties: Vec<PropertyDesc>,
}

type LayoutKey = (u128, u16, u8);

/// Cache of event layouts keyed by (provider GUID, event id, version).
///
/// A `None` entry records that TDH has no schema for this event, so we do not
/// pay for a failing `TdhGetEventInformation` on every single occurrence.
fn layout_cache() -> &'static Mutex<HashMap<LayoutKey, Option<Arc<EventLayout>>>> {
    static CACHE: OnceLock<Mutex<HashMap<LayoutKey, Option<Arc<EventLayout>>>>> = OnceLock::new();
    CACHE.get_or_init(|| Mutex::new(HashMap::new()))
}

/// Drop every cached event layout.
pub fn clear_layout_cache() {
    layout_cache().lock().clear();
}

/// Number of event layouts currently cached.
pub fn layout_cache_len() -> usize {
    layout_cache().lock().len()
}

/// Reinterpret ferrisetw's wrapper as the raw record TDH expects.
///
/// Sound because `ferrisetw::EventRecord` is declared `#[repr(transparent)]`
/// over `EVENT_RECORD`, which guarantees identical layout and ABI. ferrisetw
/// has an equivalent `as_raw_ptr()` but keeps it crate-private.
fn as_raw_record(record: &EventRecord) -> *const EVENT_RECORD {
    record as *const EventRecord as *const EVENT_RECORD
}

/// Read a NUL-terminated UTF-16 string at `offset` bytes into `buf`.
///
/// Returns `None` for a zero offset (TDH's "absent" marker) or if the string
/// would run past the end of the buffer.
fn wide_string_at(buf: &[u8], offset: u32) -> Option<String> {
    if offset == 0 || offset as usize >= buf.len() {
        return None;
    }
    let start = offset as usize;
    // The offset is a byte offset but the text is UTF-16, so an odd offset or a
    // trailing odd byte would make us read a partial code unit.
    let tail = &buf[start..];
    let units: Vec<u16> = tail
        .chunks_exact(2)
        .map(|c| u16::from_le_bytes([c[0], c[1]]))
        .take_while(|&u| u != 0)
        .collect();
    if units.is_empty() {
        return None;
    }
    Some(String::from_utf16_lossy(&units))
}

/// Call `TdhGetEventInformation` and lift the parts we need into owned data.
///
/// # Safety
///
/// `record` must point to a valid `EVENT_RECORD` that stays alive for the call.
unsafe fn read_layout(record: *const EVENT_RECORD) -> Option<EventLayout> {
    let mut size: u32 = 0;
    let status = unsafe { TdhGetEventInformation(record, None, None, &mut size) };
    if status != ERROR_INSUFFICIENT_BUFFER || size == 0 {
        // Anything else means TDH has no manifest/MOF schema for this event.
        return None;
    }

    // Over-align the backing store: TRACE_EVENT_INFO is read through a typed
    // pointer, so the allocation must satisfy its alignment, which a plain
    // Vec<u8> does not promise.
    let mut buf: Vec<u64> = vec![0u64; size.div_ceil(8) as usize];
    let info_ptr = buf.as_mut_ptr() as *mut TRACE_EVENT_INFO;

    let status = unsafe { TdhGetEventInformation(record, None, Some(info_ptr), &mut size) };
    if status != ERROR_SUCCESS {
        return None;
    }

    let bytes: &[u8] =
        unsafe { std::slice::from_raw_parts(buf.as_ptr() as *const u8, size as usize) };
    let info = unsafe { &*info_ptr };

    let count = info.TopLevelPropertyCount as usize;
    let mut properties = Vec::with_capacity(count);

    let array_ptr = std::ptr::addr_of!(info.EventPropertyInfoArray) as *const EVENT_PROPERTY_INFO;
    for i in 0..count {
        let prop = unsafe { &*array_ptr.add(i) };

        let Some(name) = wide_string_at(bytes, prop.NameOffset) else {
            continue;
        };

        let is_struct = prop.Flags.0 & PROPERTY_STRUCT != 0;
        // `nonStructType` and `structType` overlay each other; only the former
        // carries in/out types, and reading it for a struct would be nonsense.
        let (in_type, out_type) = if is_struct {
            (IN_NULL, 0)
        } else {
            let non_struct = unsafe { prop.Anonymous1.nonStructType };
            (non_struct.InType, non_struct.OutType)
        };

        let mut name_utf16: Vec<u16> = name.encode_utf16().collect();
        name_utf16.push(0);

        properties.push(PropertyDesc {
            name,
            name_utf16,
            in_type,
            out_type,
            is_struct,
        });
    }

    Some(EventLayout { properties })
}

/// Fetch the layout for this event, consulting and populating the cache.
fn layout_for(record: &EventRecord, raw: *const EVENT_RECORD) -> Option<Arc<EventLayout>> {
    let key: LayoutKey = (
        record.provider_id().to_u128(),
        record.event_id(),
        record.version(),
    );

    if let Some(cached) = layout_cache().lock().get(&key) {
        return cached.clone();
    }

    let layout = unsafe { read_layout(raw) }.map(Arc::new);
    layout_cache().lock().insert(key, layout.clone());
    layout
}

/// Retrieve one property's raw bytes by name.
///
/// # Safety
///
/// `record` must point to a valid `EVENT_RECORD` that stays alive for the call.
unsafe fn property_bytes(record: *const EVENT_RECORD, name_utf16: &[u16]) -> Option<Vec<u8>> {
    let descriptor = PROPERTY_DATA_DESCRIPTOR {
        PropertyName: name_utf16.as_ptr() as u64,
        // 0xFFFF_FFFF asks for the whole property rather than one array element.
        ArrayIndex: u32::MAX,
        Reserved: 0,
    };
    let descriptors = [descriptor];

    let mut size: u32 = 0;
    let status = unsafe { TdhGetPropertySize(record, None, &descriptors, &mut size) };
    if status != ERROR_SUCCESS {
        return None;
    }
    if size == 0 {
        return Some(Vec::new());
    }

    let mut buf = vec![0u8; size as usize];
    let status = unsafe { TdhGetProperty(record, None, &descriptors, &mut buf) };
    if status != ERROR_SUCCESS {
        return None;
    }
    Some(buf)
}

/// Decode a UTF-16 blob, trimming a trailing NUL if the provider included one.
fn decode_utf16(bytes: &[u8]) -> String {
    let units: Vec<u16> = bytes
        .chunks_exact(2)
        .map(|c| u16::from_le_bytes([c[0], c[1]]))
        .collect();
    let units = units.strip_suffix(&[0u16]).unwrap_or(&units);
    String::from_utf16_lossy(units)
}

/// Decode an 8-bit blob, trimming a trailing NUL if the provider included one.
fn decode_ansi(bytes: &[u8]) -> String {
    let bytes = bytes.strip_suffix(&[0u8]).unwrap_or(bytes);
    String::from_utf8_lossy(bytes).into_owned()
}

/// Format a binary SID as the conventional `S-1-5-...` string.
fn format_sid(bytes: &[u8]) -> Option<String> {
    // SID layout: revision(1) subauthority count(1) identifier authority(6)
    // then that many little-endian u32 sub-authorities.
    if bytes.len() < 8 {
        return None;
    }
    let revision = bytes[0];
    let sub_count = bytes[1] as usize;
    if bytes.len() < 8 + sub_count * 4 {
        return None;
    }
    // The identifier authority is big-endian, unlike everything after it.
    let authority = bytes[2..8]
        .iter()
        .fold(0u64, |acc, &b| (acc << 8) | u64::from(b));

    let mut out = format!("S-{}-{}", revision, authority);
    for i in 0..sub_count {
        let off = 8 + i * 4;
        let value =
            u32::from_le_bytes([bytes[off], bytes[off + 1], bytes[off + 2], bytes[off + 3]]);
        out.push_str(&format!("-{}", value));
    }
    Some(out)
}

/// Build a GUID string from its little-endian on-the-wire layout.
fn decode_guid(bytes: &[u8]) -> Option<Uuid> {
    if bytes.len() < 16 {
        return None;
    }
    let d1 = u32::from_le_bytes([bytes[0], bytes[1], bytes[2], bytes[3]]);
    let d2 = u16::from_le_bytes([bytes[4], bytes[5]]);
    let d3 = u16::from_le_bytes([bytes[6], bytes[7]]);
    let mut d4 = [0u8; 8];
    d4.copy_from_slice(&bytes[8..16]);
    Some(Uuid::from_fields(d1, d2, d3, &d4))
}

/// Convert a Windows `FILETIME` (100 ns ticks since 1601) to a UTC timestamp.
fn filetime_to_utc(ticks: i64) -> Option<chrono::DateTime<Utc>> {
    const EPOCH_DELTA_100NS: i64 = 116_444_736_000_000_000;
    let unix_100ns = ticks.checked_sub(EPOCH_DELTA_100NS)?;
    let secs = unix_100ns.div_euclid(10_000_000);
    let nanos = (unix_100ns.rem_euclid(10_000_000) * 100) as u32;
    Utc.timestamp_opt(secs, nanos).single()
}

/// Decode a `SYSTEMTIME` structure: eight little-endian u16 fields.
fn decode_systemtime(bytes: &[u8]) -> Option<chrono::DateTime<Utc>> {
    if bytes.len() < 16 {
        return None;
    }
    let f = |i: usize| u16::from_le_bytes([bytes[i * 2], bytes[i * 2 + 1]]) as u32;
    let (year, month, day) = (f(0), f(1), f(3));
    let (hour, minute, second, millis) = (f(4), f(5), f(6), f(7));
    Utc.with_ymd_and_hms(year as i32, month, day, hour, minute, second)
        .single()
        .map(|dt| dt + chrono::Duration::milliseconds(millis as i64))
}

macro_rules! fixed {
    ($bytes:expr, $ty:ty, $n:literal) => {{
        if $bytes.len() < $n {
            return None;
        }
        let mut a = [0u8; $n];
        a.copy_from_slice(&$bytes[..$n]);
        <$ty>::from_le_bytes(a)
    }};
}

/// Map one property's raw bytes onto an [`EventValue`] using its TDH in-type.
///
/// `pointer_size` is the pointer width of the *emitting* process, which is not
/// necessarily ours.
fn to_event_value(
    bytes: &[u8],
    in_type: u16,
    _out_type: u16,
    pointer_size: usize,
) -> Option<EventValue> {
    if bytes.is_empty() && !matches!(in_type, IN_NULL | IN_BINARY | IN_HEXDUMP) {
        return Some(EventValue::Null);
    }

    let value = match in_type {
        IN_NULL => EventValue::Null,

        IN_UNICODESTRING
        | IN_COUNTEDSTRING
        | IN_NONNULLTERMINATEDSTRING
        | IN_MANIFEST_COUNTEDSTRING
        | IN_UNICODECHAR => EventValue::String(decode_utf16(bytes)),

        IN_ANSISTRING
        | IN_COUNTEDANSISTRING
        | IN_NONNULLTERMINATEDANSISTRING
        | IN_MANIFEST_COUNTEDANSISTRING
        | IN_ANSICHAR => EventValue::String(decode_ansi(bytes)),

        IN_INT8 => EventValue::I8(bytes[0] as i8),
        IN_UINT8 => EventValue::U8(bytes[0]),
        IN_INT16 => EventValue::I16(fixed!(bytes, i16, 2)),
        IN_UINT16 => EventValue::U16(fixed!(bytes, u16, 2)),
        IN_INT32 => EventValue::I32(fixed!(bytes, i32, 4)),
        IN_UINT32 | IN_HEXINT32 => EventValue::U32(fixed!(bytes, u32, 4)),
        IN_INT64 => EventValue::I64(fixed!(bytes, i64, 8)),
        IN_UINT64 | IN_HEXINT64 => EventValue::U64(fixed!(bytes, u64, 8)),
        IN_FLOAT => EventValue::F32(fixed!(bytes, f32, 4)),
        IN_DOUBLE => EventValue::F64(fixed!(bytes, f64, 8)),

        // A Win32 BOOL is a 32-bit value, not a byte.
        IN_BOOLEAN => EventValue::Bool(fixed!(bytes, u32, 4) != 0),

        IN_BINARY | IN_HEXDUMP | IN_MANIFEST_COUNTEDBINARY => EventValue::Binary(bytes.to_vec()),

        IN_GUID => EventValue::Guid(decode_guid(bytes)?),

        IN_POINTER | IN_SIZET => {
            if pointer_size == 4 {
                EventValue::Pointer(u64::from(fixed!(bytes, u32, 4)))
            } else {
                EventValue::Pointer(fixed!(bytes, u64, 8))
            }
        }

        IN_FILETIME => {
            let ticks = fixed!(bytes, i64, 8);
            match filetime_to_utc(ticks) {
                Some(dt) => EventValue::SystemTime(dt),
                None => EventValue::FileTime(ticks),
            }
        }

        IN_SYSTEMTIME => EventValue::SystemTime(decode_systemtime(bytes)?),

        IN_SID => EventValue::Sid(format_sid(bytes)?),

        // Unknown or not yet handled: keep the bytes rather than drop the
        // property, so nothing silently disappears the way it used to.
        _ => EventValue::Binary(bytes.to_vec()),
    };

    Some(value)
}

/// Parse every top-level property of an event.
///
/// Returns an empty map when TDH has no schema for the event, which is normal
/// for WPP and for providers with no manifest installed.
pub fn parse_properties(record: &EventRecord) -> HashMap<String, EventValue> {
    let raw = as_raw_record(record);

    let Some(layout) = layout_for(record, raw) else {
        return HashMap::new();
    };

    let pointer_size = if record.event_flags() & EVENT_HEADER_FLAG_32_BIT_HEADER != 0 {
        4
    } else {
        8
    };

    let mut out = HashMap::with_capacity(layout.properties.len());
    for prop in &layout.properties {
        // Nested structures are left to a follow-up; skipping them keeps the
        // scalar properties around them intact.
        if prop.is_struct {
            continue;
        }
        let Some(bytes) = (unsafe { property_bytes(raw, &prop.name_utf16) }) else {
            continue;
        };
        if let Some(value) = to_event_value(&bytes, prop.in_type, prop.out_type, pointer_size) {
            out.insert(prop.name.clone(), value);
        }
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_decode_utf16_trims_trailing_nul() {
        let bytes: Vec<u8> = "abc\0".encode_utf16().flat_map(u16::to_le_bytes).collect();
        assert_eq!(decode_utf16(&bytes), "abc");
    }

    #[test]
    fn test_decode_utf16_without_nul() {
        let bytes: Vec<u8> = "abc".encode_utf16().flat_map(u16::to_le_bytes).collect();
        assert_eq!(decode_utf16(&bytes), "abc");
    }

    #[test]
    fn test_decode_ansi_trims_trailing_nul() {
        assert_eq!(decode_ansi(b"hello\0"), "hello");
        assert_eq!(decode_ansi(b"hello"), "hello");
    }

    #[test]
    fn test_format_sid_local_system() {
        // S-1-5-18
        let sid = [1u8, 1, 0, 0, 0, 0, 0, 5, 18, 0, 0, 0];
        assert_eq!(format_sid(&sid).as_deref(), Some("S-1-5-18"));
    }

    #[test]
    fn test_format_sid_rejects_truncated() {
        assert!(format_sid(&[1, 1, 0, 0, 0, 0, 0, 5]).is_none());
        assert!(format_sid(&[1, 1]).is_none());
    }

    #[test]
    fn test_decode_guid_little_endian() {
        let mut bytes = [0u8; 16];
        bytes[..4].copy_from_slice(&0x1234_5678u32.to_le_bytes());
        bytes[4..6].copy_from_slice(&0x9abcu16.to_le_bytes());
        bytes[6..8].copy_from_slice(&0xdef0u16.to_le_bytes());
        bytes[8..].copy_from_slice(&[1, 2, 3, 4, 5, 6, 7, 8]);
        let guid = decode_guid(&bytes).unwrap();
        assert_eq!(guid.to_string(), "12345678-9abc-def0-0102-030405060708");
    }

    #[test]
    fn test_decode_guid_rejects_short() {
        assert!(decode_guid(&[0u8; 15]).is_none());
    }

    #[test]
    fn test_boolean_is_four_bytes() {
        let v = to_event_value(&1u32.to_le_bytes(), IN_BOOLEAN, 0, 8);
        assert!(matches!(v, Some(EventValue::Bool(true))));
        let v = to_event_value(&0u32.to_le_bytes(), IN_BOOLEAN, 0, 8);
        assert!(matches!(v, Some(EventValue::Bool(false))));
    }

    #[test]
    fn test_pointer_width_follows_emitting_process() {
        let bytes = [0xAAu8, 0xBB, 0xCC, 0xDD, 0xEE, 0xFF, 0x00, 0x11];
        assert!(matches!(
            to_event_value(&bytes, IN_POINTER, 0, 4),
            Some(EventValue::Pointer(0xDDCC_BBAA))
        ));
        assert!(matches!(
            to_event_value(&bytes, IN_POINTER, 0, 8),
            Some(EventValue::Pointer(0x1100_FFEE_DDCC_BBAA))
        ));
    }

    #[test]
    fn test_unknown_in_type_keeps_bytes() {
        let v = to_event_value(&[1, 2, 3], 9999, 0, 8);
        assert!(matches!(v, Some(EventValue::Binary(b)) if b == vec![1, 2, 3]));
    }

    #[test]
    fn test_truncated_fixed_width_is_rejected() {
        // Two bytes cannot hold a u32; better to drop the property than to
        // report a value invented from padding.
        assert!(to_event_value(&[1, 2], IN_UINT32, 0, 8).is_none());
    }

    #[test]
    fn test_filetime_epoch() {
        let dt = filetime_to_utc(116_444_736_000_000_000).unwrap();
        assert_eq!(dt.timestamp(), 0);
    }

    #[test]
    fn test_wide_string_at_zero_offset_is_absent() {
        assert!(wide_string_at(&[0u8; 16], 0).is_none());
    }

    #[test]
    fn test_wide_string_at_out_of_range_is_absent() {
        assert!(wide_string_at(&[0u8; 4], 99).is_none());
    }

    #[test]
    fn test_wide_string_at_reads_value() {
        let mut buf = vec![0u8; 4];
        buf.extend("hi".encode_utf16().flat_map(u16::to_le_bytes));
        buf.extend_from_slice(&[0, 0]);
        assert_eq!(wide_string_at(&buf, 4).as_deref(), Some("hi"));
    }
}
