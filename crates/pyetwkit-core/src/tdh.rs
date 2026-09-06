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
use pyo3::prelude::*;
use std::collections::HashMap;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, OnceLock};
use uuid::Uuid;
use windows::core::{PCWSTR, PWSTR};
use windows::Win32::System::Diagnostics::Etw::{
    TdhFormatProperty, TdhGetEventInformation, TdhGetEventMapInformation, TdhGetProperty,
    TdhGetPropertySize, EVENT_MAP_INFO, EVENT_PROPERTY_INFO, EVENT_RECORD,
    PROPERTY_DATA_DESCRIPTOR, TDH_CONTEXT, TDH_CONTEXT_WPP_TMFSEARCHPATH, TRACE_EVENT_INFO,
};

/// `EVENT_HEADER_FLAG_32_BIT_HEADER`, used to pick the pointer width of the
/// process that emitted the event rather than of this one.
const EVENT_HEADER_FLAG_32_BIT_HEADER: u16 = 0x0020;

const ERROR_SUCCESS: u32 = 0;
const ERROR_INSUFFICIENT_BUFFER: u32 = 122;

/// `PROPERTY_FLAGS` bit marking a property as a nested structure.
const PROPERTY_STRUCT: i32 = 1;

/// `PROPERTY_FLAGS` bit meaning the element count lives in another property
/// rather than in this one's `count` field.
const PROPERTY_PARAM_COUNT: i32 = 4;

/// `PROPERTY_FLAGS` bit meaning the byte length lives in another property.
const PROPERTY_PARAM_LENGTH: i32 = 2;

/// Ceiling on how many elements we will materialise for one array property.
///
/// A fixed `count` cannot exceed `u16::MAX` anyway; the cap only matters for a
/// count read out of another property, where a malformed event could otherwise
/// ask us for an enormous allocation.
const MAX_ARRAY_ELEMENTS: u32 = u16::MAX as u32;

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

/// How many elements a property holds.
///
/// The schema either states the count outright or names another property of the
/// same event that carries it, in which case it is only known per event.
#[derive(Debug, Clone, Copy)]
enum PropertyCount {
    Fixed(u16),
    FromProperty(u16),
}

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
    count: PropertyCount,
    /// For a struct, the index of its first member in [`EventLayout::properties`].
    struct_start: u16,
    /// For a struct, how many members follow `struct_start`.
    struct_members: u16,
    /// Declared byte length, which `TdhFormatProperty` wants for fixed types.
    length: u16,
    /// Name of the value map for this property, if the schema declares one,
    /// NUL-terminated and ready for `TdhGetEventMapInformation`.
    map_name: Option<Vec<u16>>,
}

impl PropertyDesc {
    /// A stand-in for a property TDH gave no name for.
    ///
    /// It occupies the slot so that later properties keep the index the schema
    /// refers to them by, and is skipped when values are read: an unnamed
    /// property has no key to store a value under.
    fn placeholder() -> Self {
        Self {
            name: String::new(),
            name_utf16: Vec::new(),
            in_type: IN_NULL,
            out_type: 0,
            is_struct: false,
            count: PropertyCount::Fixed(1),
            struct_start: 0,
            struct_members: 0,
            length: 0,
            map_name: None,
        }
    }

    fn is_placeholder(&self) -> bool {
        self.name.is_empty()
    }
}

/// The parsed, owned form of a `TRACE_EVENT_INFO` for one event layout.
#[derive(Debug, Clone, Default)]
struct EventLayout {
    /// Every property TDH reports, positionally aligned with
    /// `EventPropertyInfoArray` so an index from the schema means the same here.
    properties: Vec<PropertyDesc>,
    /// How many of those are top level; the rest are members of some struct.
    top_level_count: usize,
}

type LayoutKey = (u128, u16, u8);

/// Directory TDH should search for WPP `.tmf` files, NUL-terminated UTF-16.
///
/// WPP events carry no schema of their own: the format strings live in a `.tmf`
/// generated from the emitting binary's PDB. Without one TDH can say nothing
/// about the event, which is why such events come back with no properties and
/// only `raw_data`. Given a search path it can decode them.
fn tmf_search_path() -> &'static Mutex<Option<Vec<u16>>> {
    static PATH: OnceLock<Mutex<Option<Vec<u16>>>> = OnceLock::new();
    PATH.get_or_init(|| Mutex::new(None))
}

/// Point TDH at a directory of WPP `.tmf` files, or pass `None` to stop.
///
/// Clears the layout cache, since whether an event has a schema is exactly what
/// this changes.
pub fn set_wpp_tmf_search_path(path: Option<&str>) {
    let encoded = path.map(|p| {
        let mut utf16: Vec<u16> = p.encode_utf16().collect();
        utf16.push(0);
        utf16
    });
    *tmf_search_path().lock() = encoded;
    clear_layout_cache();
}

/// The directory currently searched for `.tmf` files, if any.
pub fn wpp_tmf_search_path() -> Option<String> {
    tmf_search_path().lock().as_ref().map(|utf16| {
        let end = utf16.iter().position(|&u| u == 0).unwrap_or(utf16.len());
        String::from_utf16_lossy(&utf16[..end])
    })
}

/// Build the `TDH_CONTEXT` array for a decoding call.
///
/// Empty unless a TMF search path has been set, so the common path passes TDH
/// no context at all, exactly as before.
fn tdh_contexts(path: &Option<Vec<u16>>) -> Vec<TDH_CONTEXT> {
    match path {
        Some(utf16) => vec![TDH_CONTEXT {
            ParameterValue: utf16.as_ptr() as u64,
            ParameterType: TDH_CONTEXT_WPP_TMFSEARCHPATH,
            ParameterSize: 0,
        }],
        None => Vec::new(),
    }
}

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
    let (pairs, _) = tail.as_chunks::<2>();
    let units: Vec<u16> = pairs
        .iter()
        .map(|&[lo, hi]| u16::from_le_bytes([lo, hi]))
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
    // Held across both calls so the path it points at stays alive for TDH.
    let path = tmf_search_path().lock();
    let contexts = tdh_contexts(&path);
    let contexts = (!contexts.is_empty()).then_some(contexts.as_slice());

    let mut size: u32 = 0;
    let status = unsafe { TdhGetEventInformation(record, contexts, None, &mut size) };
    if status != ERROR_INSUFFICIENT_BUFFER || size == 0 {
        // Anything else means TDH has no manifest/MOF/WPP schema for this event.
        return None;
    }

    // Over-align the backing store: TRACE_EVENT_INFO is read through a typed
    // pointer, so the allocation must satisfy its alignment, which a plain
    // Vec<u8> does not promise.
    let mut buf: Vec<u64> = vec![0u64; size.div_ceil(8) as usize];
    let info_ptr = buf.as_mut_ptr() as *mut TRACE_EVENT_INFO;

    let status = unsafe { TdhGetEventInformation(record, contexts, Some(info_ptr), &mut size) };
    if status != ERROR_SUCCESS {
        return None;
    }

    let bytes: &[u8] =
        unsafe { std::slice::from_raw_parts(buf.as_ptr() as *const u8, size as usize) };
    let info = unsafe { &*info_ptr };

    // Walk every property, not just the top-level ones: members of a nested
    // structure live past `TopLevelPropertyCount`, and `structType` addresses
    // them by their index into this same array. The vector is therefore kept
    // positionally aligned with `EventPropertyInfoArray`, with a placeholder for
    // anything unnamed, so an index from the schema means the same thing here.
    let total = info.PropertyCount as usize;
    let top_level_count = (info.TopLevelPropertyCount as usize).min(total);
    let mut properties = Vec::with_capacity(total);

    let array_ptr = std::ptr::addr_of!(info.EventPropertyInfoArray) as *const EVENT_PROPERTY_INFO;
    for i in 0..total {
        let prop = unsafe { &*array_ptr.add(i) };

        let Some(name) = wide_string_at(bytes, prop.NameOffset) else {
            properties.push(PropertyDesc::placeholder());
            continue;
        };

        let is_struct = prop.Flags.0 & PROPERTY_STRUCT != 0;
        // `nonStructType` and `structType` overlay each other; only one of them
        // is meaningful, and reading the wrong one would be nonsense.
        let (in_type, out_type, struct_start, struct_members, map_name) = if is_struct {
            let s = unsafe { prop.Anonymous1.structType };
            (IN_NULL, 0, s.StructStartIndex, s.NumOfStructMembers, None)
        } else {
            let non_struct = unsafe { prop.Anonymous1.nonStructType };
            // A map turns a bare number into the name the manifest gives it.
            let map_name = wide_string_at(bytes, non_struct.MapNameOffset).map(|name| {
                let mut utf16: Vec<u16> = name.encode_utf16().collect();
                utf16.push(0);
                utf16
            });
            (non_struct.InType, non_struct.OutType, 0, 0, map_name)
        };

        // `length` and `lengthPropertyIndex` overlay each other. Only the plain
        // length is of use here, and only as a hint to `TdhFormatProperty`; the
        // value bytes themselves always come from TDH.
        let length = if prop.Flags.0 & PROPERTY_PARAM_LENGTH != 0 {
            0
        } else {
            unsafe { prop.Anonymous3.length }
        };

        // `count` and `countPropertyIndex` overlay each other; the flag says
        // which one is meaningful.
        let count = if prop.Flags.0 & PROPERTY_PARAM_COUNT != 0 {
            PropertyCount::FromProperty(unsafe { prop.Anonymous2.countPropertyIndex })
        } else {
            PropertyCount::Fixed(unsafe { prop.Anonymous2.count })
        };

        let mut name_utf16: Vec<u16> = name.encode_utf16().collect();
        name_utf16.push(0);

        properties.push(PropertyDesc {
            name,
            name_utf16,
            in_type,
            out_type,
            is_struct,
            count,
            struct_start,
            struct_members,
            length,
            map_name,
        });
    }

    Some(EventLayout {
        properties,
        top_level_count,
    })
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

/// `PROPERTY_DATA_DESCRIPTOR::ArrayIndex` value asking for a whole property
/// rather than one element of it.
const WHOLE_PROPERTY: u32 = u32::MAX;

/// One link in the path to a value: a property name and which element of it.
///
/// A top-level property needs a single link. A member of a struct needs two --
/// the struct, then the member -- and a member of a struct nested inside another
/// struct needs three, which is exactly the descriptor array TDH expects.
type PathLink<'a> = (&'a [u16], u32);

/// How deep a nesting of structures we are willing to follow.
///
/// Guards against a malformed or hostile schema whose struct members point back
/// at an enclosing struct, which would otherwise recurse without end.
const MAX_STRUCT_DEPTH: usize = 8;

/// Retrieve the raw bytes of the value `path` leads to.
///
/// # Safety
///
/// `record` must point to a valid `EVENT_RECORD` that stays alive for the call,
/// and every name in `path` must stay alive for it too.
unsafe fn property_bytes_at(record: *const EVENT_RECORD, path: &[PathLink]) -> Option<Vec<u8>> {
    if path.is_empty() {
        return None;
    }
    let descriptors: Vec<PROPERTY_DATA_DESCRIPTOR> = path
        .iter()
        .map(|(name_utf16, array_index)| PROPERTY_DATA_DESCRIPTOR {
            PropertyName: name_utf16.as_ptr() as u64,
            ArrayIndex: *array_index,
            Reserved: 0,
        })
        .collect();

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

/// Retrieve one top-level property's raw bytes by name.
///
/// `array_index` selects a single element, or [`WHOLE_PROPERTY`] for all of it.
///
/// # Safety
///
/// As [`property_bytes_at`].
unsafe fn property_bytes(
    record: *const EVENT_RECORD,
    name_utf16: &[u16],
    array_index: u32,
) -> Option<Vec<u8>> {
    unsafe { property_bytes_at(record, &[(name_utf16, array_index)]) }
}

/// Drop the two-byte length prefix a counted string or blob carries.
///
/// TDH returns that prefix as part of the value for the counted in-types, so
/// without this it is decoded as content: a TraceLogging counted string holding
/// "core-state" came back as "\u{14}core-state", the `\u{14}` being the 20-byte
/// length. The prefix is only removed when it actually describes the rest of the
/// buffer, so a provider or TDH version that hands the value over already
/// stripped is left alone rather than losing its first character.
fn strip_counted_prefix(bytes: &[u8]) -> &[u8] {
    if bytes.len() >= 2 {
        let declared = u16::from_le_bytes([bytes[0], bytes[1]]) as usize;
        if declared == bytes.len() - 2 {
            return &bytes[2..];
        }
    }
    bytes
}

/// Decode a UTF-16 blob, trimming a trailing NUL if the provider included one.
fn decode_utf16(bytes: &[u8]) -> String {
    let (pairs, _) = bytes.as_chunks::<2>();
    let units: Vec<u16> = pairs
        .iter()
        .map(|&[lo, hi]| u16::from_le_bytes([lo, hi]))
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

    // The authority is six bytes wide but is conventionally written in decimal,
    // and `ConvertSidToStringSidW` switches to unpadded uppercase hex once the
    // value no longer fits in 32 bits. Match that, so a SID we print can be fed
    // straight back to Windows.
    let mut out = if authority > u64::from(u32::MAX) {
        format!("S-{}-0x{:X}", revision, authority)
    } else {
        format!("S-{}-{}", revision, authority)
    };
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

        IN_UNICODESTRING | IN_NONNULLTERMINATEDSTRING | IN_UNICODECHAR => {
            EventValue::String(decode_utf16(bytes))
        }

        IN_COUNTEDSTRING | IN_MANIFEST_COUNTEDSTRING => {
            EventValue::String(decode_utf16(strip_counted_prefix(bytes)))
        }

        IN_ANSISTRING | IN_NONNULLTERMINATEDANSISTRING | IN_ANSICHAR => {
            EventValue::String(decode_ansi(bytes))
        }

        IN_COUNTEDANSISTRING | IN_MANIFEST_COUNTEDANSISTRING => {
            EventValue::String(decode_ansi(strip_counted_prefix(bytes)))
        }

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

        IN_BINARY | IN_HEXDUMP => EventValue::Binary(bytes.to_vec()),

        IN_MANIFEST_COUNTEDBINARY => EventValue::Binary(strip_counted_prefix(bytes).to_vec()),

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

/// Byte width of one element, for in-types whose values are always that wide.
///
/// `None` means the width depends on the data (strings, blobs), so elements can
/// only be located by TDH and not by arithmetic here.
fn fixed_element_size(in_type: u16, pointer_size: usize) -> Option<usize> {
    Some(match in_type {
        IN_INT8 | IN_UINT8 => 1,
        IN_INT16 | IN_UINT16 => 2,
        IN_INT32 | IN_UINT32 | IN_HEXINT32 | IN_FLOAT | IN_BOOLEAN => 4,
        IN_INT64 | IN_UINT64 | IN_HEXINT64 | IN_DOUBLE | IN_FILETIME => 8,
        IN_GUID | IN_SYSTEMTIME => 16,
        IN_POINTER | IN_SIZET => pointer_size,
        _ => return None,
    })
}

/// Whether an in-type already consumes a whole multi-element blob correctly.
///
/// A `count` of N on these means "N characters" or "N bytes", i.e. one value
/// spanning the blob, not N separate values, so they must not be split up.
fn spans_whole_blob(in_type: u16) -> bool {
    matches!(
        in_type,
        IN_UNICODECHAR | IN_ANSICHAR | IN_BINARY | IN_HEXDUMP | IN_MANIFEST_COUNTEDBINARY
    )
}

/// Read a little-endian unsigned integer of whatever width the slice happens to
/// be, used for a count that one property borrows from another.
fn read_unsigned(bytes: &[u8]) -> Option<u64> {
    Some(match bytes.len() {
        1 => u64::from(bytes[0]),
        2 => u64::from(u16::from_le_bytes([bytes[0], bytes[1]])),
        4 => u64::from(u32::from_le_bytes([bytes[0], bytes[1], bytes[2], bytes[3]])),
        8 => u64::from_le_bytes(bytes[..8].try_into().ok()?),
        _ => return None,
    })
}

/// Resolve how many elements `prop` holds in this particular event.
fn element_count<'a>(
    record: *const EVENT_RECORD,
    layout: &'a EventLayout,
    prop: &PropertyDesc,
    parent: &[PathLink<'a>],
) -> u32 {
    let raw_count = match prop.count {
        PropertyCount::Fixed(n) => u32::from(n),
        PropertyCount::FromProperty(index) => {
            // `countPropertyIndex` indexes the schema's own property array, and
            // `layout.properties` is kept aligned with it, so this is the
            // property the schema meant. An index past the end (or an unnamed
            // slot) leaves the count at 1.
            match layout.properties.get(index as usize) {
                Some(counter) if !counter.is_placeholder() => {
                    // The counter is a sibling of `prop`, so it is reached
                    // through the same enclosing struct. Fall back to the top
                    // level for schemas that point outside the struct.
                    let mut path = parent.to_vec();
                    path.push((&counter.name_utf16, leaf_index(parent, 0)));
                    unsafe { property_bytes_at(record, &path) }
                        .or_else(|| unsafe {
                            property_bytes(record, &counter.name_utf16, WHOLE_PROPERTY)
                        })
                        .as_deref()
                        .and_then(read_unsigned)
                        .and_then(|n| u32::try_from(n).ok())
                        // A count we cannot read is treated as a plain scalar,
                        // which is what this code did before arrays existed.
                        .unwrap_or(1)
                }
                _ => 1,
            }
        }
    };
    raw_count.min(MAX_ARRAY_ELEMENTS)
}

/// `ArrayIndex` to use for the last link of a path.
///
/// At the top level TDH accepts [`WHOLE_PROPERTY`], which is how a whole array
/// is fetched in one call. Inside a struct the element has to be named
/// concretely, so `index` is used instead.
fn leaf_index(parent: &[PathLink], index: u32) -> u32 {
    if parent.is_empty() {
        WHOLE_PROPERTY
    } else {
        index
    }
}

/// Read one property's value, following `parent` to the enclosing struct
/// element; `parent` is empty for a top-level property.
fn read_value<'a>(
    record: *const EVENT_RECORD,
    layout: &'a EventLayout,
    prop: &'a PropertyDesc,
    parent: &[PathLink<'a>],
    pointer_size: usize,
    depth: usize,
) -> Option<EventValue> {
    let count = element_count(record, layout, prop, parent);

    if prop.is_struct {
        // A schema whose members loop back to an enclosing struct would recurse
        // forever; stop rather than trust it.
        if depth >= MAX_STRUCT_DEPTH {
            return None;
        }
        if count <= 1 {
            return read_struct(record, layout, prop, parent, 0, pointer_size, depth);
        }
        let mut items = Vec::with_capacity(count as usize);
        for index in 0..count {
            let Some(value) = read_struct(record, layout, prop, parent, index, pointer_size, depth)
            else {
                break;
            };
            items.push(value);
        }
        return Some(EventValue::Array(items));
    }

    if parent.is_empty() {
        // Top level: fetch the whole property in one call, then split it if it
        // turns out to be an array. Without the split an array collapsed to its
        // first element -- a 176-byte array of UInt8 came back as just 228.
        let bytes = unsafe { property_bytes(record, &prop.name_utf16, WHOLE_PROPERTY) }?;
        return if count > 1 && !spans_whole_blob(prop.in_type) {
            to_event_array(record, prop, &bytes, count, pointer_size)
        } else {
            to_event_value(&bytes, prop.in_type, prop.out_type, pointer_size)
        };
    }

    // Inside a struct every element is addressed explicitly, so there is no
    // whole-blob shortcut to take.
    if count > 1 && !spans_whole_blob(prop.in_type) {
        let mut items = Vec::with_capacity(count as usize);
        for index in 0..count {
            let mut path = parent.to_vec();
            path.push((&prop.name_utf16, index));
            let Some(bytes) = (unsafe { property_bytes_at(record, &path) }) else {
                break;
            };
            let Some(value) = to_event_value(&bytes, prop.in_type, prop.out_type, pointer_size)
            else {
                break;
            };
            items.push(value);
        }
        return Some(EventValue::Array(items));
    }

    let mut path = parent.to_vec();
    path.push((&prop.name_utf16, 0));
    let bytes = unsafe { property_bytes_at(record, &path) }?;
    to_event_value(&bytes, prop.in_type, prop.out_type, pointer_size)
}

/// Read one element of a struct property into a map of member name to value.
fn read_struct<'a>(
    record: *const EVENT_RECORD,
    layout: &'a EventLayout,
    prop: &'a PropertyDesc,
    parent: &[PathLink<'a>],
    index: u32,
    pointer_size: usize,
    depth: usize,
) -> Option<EventValue> {
    let mut path = parent.to_vec();
    path.push((&prop.name_utf16, index));

    let start = prop.struct_start as usize;
    let end = start
        .saturating_add(prop.struct_members as usize)
        .min(layout.properties.len());
    if start >= end {
        return None;
    }

    let mut members = HashMap::with_capacity(end - start);
    for member in &layout.properties[start..end] {
        if member.is_placeholder() {
            continue;
        }
        if let Some(value) = read_value(record, layout, member, &path, pointer_size, depth + 1) {
            members.insert(member.name.clone(), value);
        }
    }
    Some(EventValue::Struct(members))
}

/// Decode a property that carries more than one element.
///
/// Prefers slicing the single blob we already fetched, falling back to asking
/// TDH for each element when their width is not known up front.
fn to_event_array(
    record: *const EVENT_RECORD,
    prop: &PropertyDesc,
    whole: &[u8],
    count: u32,
    pointer_size: usize,
) -> Option<EventValue> {
    let n = count as usize;

    // A byte array reaches Python far more usefully as `bytes` than as a list of
    // several hundred small ints, and that is exactly what `Binary` already does.
    if prop.in_type == IN_UINT8 && whole.len() >= n {
        return Some(EventValue::Binary(whole[..n].to_vec()));
    }

    let mut items = Vec::with_capacity(n);

    if let Some(size) = fixed_element_size(prop.in_type, pointer_size) {
        if size > 0 && whole.len() >= size * n {
            for chunk in whole.chunks_exact(size).take(n) {
                items.push(to_event_value(
                    chunk,
                    prop.in_type,
                    prop.out_type,
                    pointer_size,
                )?);
            }
            return Some(EventValue::Array(items));
        }
    }

    // Variable-width elements: only TDH knows where each one starts. Stop at the
    // first element it cannot produce and keep the ones already decoded, rather
    // than discarding the whole property.
    for index in 0..count {
        let Some(bytes) = (unsafe { property_bytes(record, &prop.name_utf16, index) }) else {
            break;
        };
        let Some(value) = to_event_value(&bytes, prop.in_type, prop.out_type, pointer_size) else {
            break;
        };
        items.push(value);
    }

    Some(EventValue::Array(items))
}

/// Whether events should also carry TDH's own display strings.
///
/// Off by default: typed values are what the exporters want, and rendering every
/// property twice costs a `TdhGetEventInformation` plus a `TdhFormatProperty`
/// per property on top of the parse.
static FORMAT_PROPERTIES: AtomicBool = AtomicBool::new(false);

/// Turn TDH's display strings on or off for events parsed from now on.
pub fn set_property_formatting(enabled: bool) {
    FORMAT_PROPERTIES.store(enabled, Ordering::Relaxed);
}

/// Whether TDH display strings are currently being produced.
pub fn property_formatting() -> bool {
    FORMAT_PROPERTIES.load(Ordering::Relaxed)
}

/// Look up the value map named by a property, if it has one.
///
/// A map turns a bare number into the name the manifest gives it, which is the
/// part of `TdhFormatProperty`'s output that typed values cannot express.
///
/// # Safety
///
/// `record` must point to a valid `EVENT_RECORD` that stays alive for the call.
unsafe fn map_info(record: *const EVENT_RECORD, map_name: &[u16]) -> Option<Vec<u64>> {
    let name = PCWSTR(map_name.as_ptr());
    let mut size: u32 = 0;
    let status = unsafe { TdhGetEventMapInformation(record, name, None, &mut size) };
    if status != ERROR_INSUFFICIENT_BUFFER || size == 0 {
        return None;
    }
    // Over-aligned for the same reason as TRACE_EVENT_INFO.
    let mut buf: Vec<u64> = vec![0u64; size.div_ceil(8) as usize];
    let ptr = buf.as_mut_ptr() as *mut EVENT_MAP_INFO;
    let status = unsafe { TdhGetEventMapInformation(record, name, Some(ptr), &mut size) };
    if status != ERROR_SUCCESS {
        return None;
    }
    Some(buf)
}

/// Render one already-isolated property value the way TDH would display it.
///
/// The bytes come from `TdhGetProperty`, so this hands `TdhFormatProperty` a
/// single value rather than walking the event payload with running offsets. That
/// walk is the part the rest of this module avoids on purpose, and skipping it
/// costs nothing here because TDH has already found the value for us.
///
/// # Safety
///
/// `info` must point to the `TRACE_EVENT_INFO` describing this event.
unsafe fn format_one(
    info: *const TRACE_EVENT_INFO,
    map: Option<*const EVENT_MAP_INFO>,
    pointer_size: usize,
    prop: &PropertyDesc,
    bytes: &[u8],
) -> Option<String> {
    if bytes.is_empty() {
        return None;
    }
    let length = if prop.length != 0 {
        prop.length
    } else {
        u16::try_from(bytes.len()).ok()?
    };

    let mut size: u32 = 0;
    let mut consumed: u16 = 0;
    let status = unsafe {
        TdhFormatProperty(
            info,
            map,
            pointer_size as u32,
            prop.in_type,
            prop.out_type,
            length,
            bytes,
            &mut size,
            None,
            &mut consumed,
        )
    };
    if status != ERROR_INSUFFICIENT_BUFFER || size == 0 {
        return None;
    }

    let mut out: Vec<u16> = vec![0u16; (size as usize).div_ceil(2)];
    let status = unsafe {
        TdhFormatProperty(
            info,
            map,
            pointer_size as u32,
            prop.in_type,
            prop.out_type,
            length,
            bytes,
            &mut size,
            Some(PWSTR(out.as_mut_ptr())),
            &mut consumed,
        )
    };
    if status != ERROR_SUCCESS {
        return None;
    }

    let end = out.iter().position(|&u| u == 0).unwrap_or(out.len());
    Some(String::from_utf16_lossy(&out[..end]))
}

/// The event's raw user data, copied out of the `EVENT_RECORD`.
///
/// ferrisetw keeps its own `user_buffer` crate-private, which is why
/// `EtwEvent.raw_data` went unpopulated; the record TDH is handed carries the
/// same bytes, so read them from there.
pub fn raw_user_data(record: &EventRecord) -> Option<Vec<u8>> {
    let raw = as_raw_record(record);
    // Safety: `record` is a live `EVENT_RECORD` for the duration of the call,
    // and `UserDataLength` is the length ETW itself recorded for `UserData`.
    unsafe {
        let len = (*raw).UserDataLength as usize;
        let ptr = (*raw).UserData as *const u8;
        if len == 0 || ptr.is_null() {
            return None;
        }
        Some(std::slice::from_raw_parts(ptr, len).to_vec())
    }
}

/// Render each top-level property the way TDH itself would display it.
///
/// This is the string view #72 asks about, offered alongside the typed values
/// rather than instead of them: typed values are what the Parquet/Arrow
/// exporters need, while these are what a human reading a trace wants, because
/// TDH resolves value maps here -- a bare `1` becomes the name the manifest
/// gives it.
///
/// Empty unless [`set_property_formatting`] has been called, and empty for
/// events TDH has no schema for. Struct-typed properties are skipped: their
/// members are values in their own right, and a single string for the whole
/// struct would be less useful than the typed map already returned.
pub fn format_properties(record: &EventRecord) -> HashMap<String, String> {
    if !property_formatting() {
        return HashMap::new();
    }
    let raw = as_raw_record(record);
    let Some(layout) = layout_for(record, raw) else {
        return HashMap::new();
    };

    // `TdhFormatProperty` wants the TRACE_EVENT_INFO itself, which the cache
    // deliberately does not retain -- keeping every event's raw schema buffer
    // alive would cost far more than re-reading it on the opt-in path.
    let Some(mut info_buf) = (unsafe { read_event_information(raw) }) else {
        return HashMap::new();
    };
    let info = info_buf.as_mut_ptr() as *const TRACE_EVENT_INFO;

    let pointer_size = pointer_size_of(record);

    let mut out = HashMap::with_capacity(layout.top_level_count);
    for prop in layout.properties.iter().take(layout.top_level_count) {
        if prop.is_placeholder() || prop.is_struct {
            continue;
        }
        // `TdhFormatProperty` renders one value, so handing it a whole array
        // would silently describe only the first element. Arrays and structs are
        // both left to `properties`, which reports every element.
        let count = element_count(raw, &layout, prop, &[]);
        if count > 1 && !spans_whole_blob(prop.in_type) {
            continue;
        }
        let Some(bytes) = (unsafe { property_bytes(raw, &prop.name_utf16, WHOLE_PROPERTY) }) else {
            continue;
        };
        let map_buf = prop
            .map_name
            .as_ref()
            .and_then(|name| unsafe { map_info(raw, name) });
        let map = map_buf
            .as_ref()
            .map(|b| b.as_ptr() as *const EVENT_MAP_INFO);

        if let Some(text) = unsafe { format_one(info, map, pointer_size, prop, &bytes) } {
            out.insert(prop.name.clone(), text);
        }
    }
    out
}

/// Pointer width of the process that emitted the event, not of this one.
fn pointer_size_of(record: &EventRecord) -> usize {
    if record.event_flags() & EVENT_HEADER_FLAG_32_BIT_HEADER != 0 {
        4
    } else {
        8
    }
}

/// Fetch the raw `TRACE_EVENT_INFO` for an event, over-aligned.
///
/// # Safety
///
/// `record` must point to a valid `EVENT_RECORD` that stays alive for the call.
unsafe fn read_event_information(record: *const EVENT_RECORD) -> Option<Vec<u64>> {
    let path = tmf_search_path().lock();
    let contexts = tdh_contexts(&path);
    let contexts = (!contexts.is_empty()).then_some(contexts.as_slice());

    let mut size: u32 = 0;
    let status = unsafe { TdhGetEventInformation(record, contexts, None, &mut size) };
    if status != ERROR_INSUFFICIENT_BUFFER || size == 0 {
        return None;
    }
    let mut buf: Vec<u64> = vec![0u64; size.div_ceil(8) as usize];
    let ptr = buf.as_mut_ptr() as *mut TRACE_EVENT_INFO;
    let status = unsafe { TdhGetEventInformation(record, contexts, Some(ptr), &mut size) };
    if status != ERROR_SUCCESS {
        return None;
    }
    Some(buf)
}

/// Whether TDH can describe this event at all.
///
/// False for WPP without a matching TMF, and for manifest providers whose
/// manifest is not installed on this machine. Those events have no property
/// names to report, so their payload is only reachable as raw bytes.
pub fn has_schema(record: &EventRecord) -> bool {
    let raw = as_raw_record(record);
    layout_for(record, raw).is_some()
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

    // Only the top-level properties become keys of the returned map. The rest of
    // the vector is the members of those properties' structs, reached through
    // them rather than reported alongside them.
    let mut out = HashMap::with_capacity(layout.top_level_count);
    for prop in layout.properties.iter().take(layout.top_level_count) {
        if prop.is_placeholder() {
            continue;
        }
        if let Some(value) = read_value(raw, &layout, prop, &[], pointer_size, 0) {
            out.insert(prop.name.clone(), value);
        }
    }
    out
}

/// Turn TDH's display strings on or off for events parsed from now on.
///
/// Off by default. Typed values stay in `properties` either way; this only adds
/// `formatted_properties`, and costs an extra TDH round trip per property.
#[pyfunction]
pub fn py_set_property_formatting(enabled: bool) {
    set_property_formatting(enabled);
}

/// Whether TDH display strings are currently being produced.
#[pyfunction]
pub fn py_property_formatting() -> bool {
    property_formatting()
}

/// Point TDH at a directory of WPP `.tmf` files, or pass `None` to stop.
///
/// WPP events carry no schema of their own, so without a matching `.tmf` they
/// arrive with no properties and only `raw_data`. Clears the schema cache.
#[pyfunction]
#[pyo3(signature = (path=None))]
pub fn py_set_wpp_tmf_search_path(path: Option<&str>) {
    set_wpp_tmf_search_path(path);
}

/// The directory currently searched for `.tmf` files, if any.
#[pyfunction]
pub fn py_wpp_tmf_search_path() -> Option<String> {
    wpp_tmf_search_path()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_counted_string_drops_its_length_prefix() {
        // TDH hands the two-byte count back as part of the value, so without
        // stripping it "core-state" decoded as "\u{14}core-state".
        let mut bytes = 20u16.to_le_bytes().to_vec();
        bytes.extend("core-state".encode_utf16().flat_map(u16::to_le_bytes));
        let v = to_event_value(&bytes, IN_COUNTEDSTRING, 0, 8);
        assert!(matches!(v, Some(EventValue::String(s)) if s == "core-state"));
    }

    #[test]
    fn test_plain_string_keeps_every_character() {
        // A non-counted type must never lose its first character to the strip.
        let bytes: Vec<u8> = "core-state"
            .encode_utf16()
            .flat_map(u16::to_le_bytes)
            .collect();
        let v = to_event_value(&bytes, IN_UNICODESTRING, 0, 8);
        assert!(matches!(v, Some(EventValue::String(s)) if s == "core-state"));
    }

    #[test]
    fn test_counted_prefix_is_left_alone_when_it_does_not_fit() {
        // Only a prefix that actually describes the rest of the buffer is a
        // length, so a value TDH already stripped survives intact.
        let bytes: Vec<u8> = "ab".encode_utf16().flat_map(u16::to_le_bytes).collect();
        assert_eq!(strip_counted_prefix(&bytes), bytes.as_slice());
    }

    #[test]
    fn test_property_formatting_is_off_by_default_and_togglable() {
        assert!(!property_formatting());
        set_property_formatting(true);
        assert!(property_formatting());
        set_property_formatting(false);
        assert!(!property_formatting());
    }

    #[test]
    fn test_tmf_search_path_round_trips() {
        assert_eq!(wpp_tmf_search_path(), None);
        set_wpp_tmf_search_path(Some(r"C:\tmf"));
        assert_eq!(wpp_tmf_search_path().as_deref(), Some(r"C:\tmf"));
        set_wpp_tmf_search_path(None);
        assert_eq!(wpp_tmf_search_path(), None);
    }

    #[test]
    fn test_no_tmf_path_means_no_tdh_context() {
        // The common path must hand TDH nothing, exactly as before the WPP
        // search path existed.
        assert!(tdh_contexts(&None).is_empty());
        let path: Vec<u16> = "x\0".encode_utf16().collect();
        let contexts = tdh_contexts(&Some(path));
        assert_eq!(contexts.len(), 1);
        assert_eq!(contexts[0].ParameterType, TDH_CONTEXT_WPP_TMFSEARCHPATH);
    }

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
    fn test_format_sid_mandatory_label() {
        // The real MandatoryLabel payload of a Kernel-Process ProcessStart event:
        // authority 16 big-endian, sub-authority 12288 little-endian.
        let sid = [1u8, 1, 0, 0, 0, 0, 0, 16, 0, 0x30, 0, 0];
        assert_eq!(format_sid(&sid).as_deref(), Some("S-1-16-12288"));
    }

    #[test]
    fn test_format_sid_large_authority_uses_hex() {
        // Windows' own ConvertSidToStringSidW renders an identifier authority
        // that does not fit in 32 bits as unpadded uppercase hex.
        let sid = [1u8, 1, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0];
        assert_eq!(format_sid(&sid).as_deref(), Some("S-1-0x100000000-1"));

        let sid = [1u8, 1, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 1, 0, 0, 0];
        assert_eq!(format_sid(&sid).as_deref(), Some("S-1-0xFFFFFFFFFFFF-1"));
    }

    #[test]
    fn test_format_sid_stays_decimal_just_below_the_hex_boundary() {
        let sid = [1u8, 1, 0, 0, 0xff, 0xff, 0xff, 0xff, 1, 0, 0, 0];
        assert_eq!(format_sid(&sid).as_deref(), Some("S-1-4294967295-1"));
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

    /// Build a `PropertyDesc` for the array tests; only the fields the array
    /// path reads actually matter.
    fn array_desc(in_type: u16, count: u16) -> PropertyDesc {
        PropertyDesc {
            name: "Prop".to_string(),
            name_utf16: "Prop\0".encode_utf16().collect(),
            in_type,
            out_type: 0,
            is_struct: false,
            count: PropertyCount::Fixed(count),
            struct_start: 0,
            struct_members: 0,
            length: 0,
            map_name: None,
        }
    }

    #[test]
    fn test_uint8_array_becomes_bytes_not_its_first_element() {
        // The regression: TimeZoneInformation is UInt8 x 176, and used to come
        // back as the single number 228.
        let blob: Vec<u8> = (0..176u32).map(|i| (i % 251) as u8).collect();
        let desc = array_desc(IN_UINT8, 176);
        let value = to_event_array(std::ptr::null(), &desc, &blob, 176, 8);
        match value {
            Some(EventValue::Binary(b)) => assert_eq!(b, blob),
            other => panic!("expected the whole blob, got {other:?}"),
        }
    }

    #[test]
    fn test_fixed_width_array_is_split_into_elements() {
        let mut blob = Vec::new();
        for n in [1u32, 2, 3, 4] {
            blob.extend_from_slice(&n.to_le_bytes());
        }
        let desc = array_desc(IN_UINT32, 4);
        let value = to_event_array(std::ptr::null(), &desc, &blob, 4, 8);
        match value {
            Some(EventValue::Array(items)) => {
                assert_eq!(items.len(), 4);
                assert!(matches!(items[0], EventValue::U32(1)));
                assert!(matches!(items[3], EventValue::U32(4)));
            }
            other => panic!("expected four elements, got {other:?}"),
        }
    }

    #[test]
    fn test_pointer_array_follows_the_emitting_process_width() {
        let blob = [1u8, 0, 0, 0, 2, 0, 0, 0];
        let desc = array_desc(IN_POINTER, 2);
        match to_event_array(std::ptr::null(), &desc, &blob, 2, 4) {
            Some(EventValue::Array(items)) => {
                assert_eq!(items.len(), 2);
                assert!(matches!(items[0], EventValue::Pointer(1)));
                assert!(matches!(items[1], EventValue::Pointer(2)));
            }
            other => panic!("expected two 32-bit pointers, got {other:?}"),
        }
    }

    #[test]
    fn test_char_array_stays_one_string() {
        // count on a UnicodeChar property means "this many characters", so the
        // blob is a single string rather than an array of one-char strings.
        assert!(spans_whole_blob(IN_UNICODECHAR));
        assert!(spans_whole_blob(IN_BINARY));
        assert!(!spans_whole_blob(IN_UINT32));
    }

    #[test]
    fn test_leaf_index_depends_on_nesting() {
        // At the top level a whole array can be fetched in one call; inside a
        // struct TDH needs the element named explicitly.
        assert_eq!(leaf_index(&[], 3), WHOLE_PROPERTY);
        let parent: Vec<PathLink> = vec![(&[0u16], 0)];
        assert_eq!(leaf_index(&parent, 3), 3);
    }

    #[test]
    fn test_placeholder_holds_its_slot_without_being_reported() {
        let p = PropertyDesc::placeholder();
        assert!(p.is_placeholder());
        assert!(!array_desc(IN_UINT32, 1).is_placeholder());
    }

    #[test]
    fn test_count_from_an_unnamed_property_falls_back_to_one() {
        // The counter resolves to a placeholder, so there is no name to fetch by
        // and the property is treated as a scalar. Reaching TDH here would
        // dereference the null record, so passing proves it short-circuits.
        let layout = EventLayout {
            properties: vec![PropertyDesc::placeholder()],
            top_level_count: 1,
        };
        let mut prop = array_desc(IN_UINT32, 0);
        prop.count = PropertyCount::FromProperty(0);
        assert_eq!(element_count(std::ptr::null(), &layout, &prop, &[]), 1);
    }

    #[test]
    fn test_count_from_an_out_of_range_index_falls_back_to_one() {
        // `countPropertyIndex` can point past the top-level properties into
        // struct members that are not in the vector at all.
        let layout = EventLayout {
            properties: vec![PropertyDesc::placeholder()],
            top_level_count: 1,
        };
        let mut prop = array_desc(IN_UINT32, 0);
        prop.count = PropertyCount::FromProperty(99);
        assert_eq!(element_count(std::ptr::null(), &layout, &prop, &[]), 1);
    }

    #[test]
    fn test_struct_recursion_is_bounded() {
        // A schema whose struct members point back at the struct would other-
        // wise recurse forever; the depth guard returns before touching TDH.
        let mut prop = array_desc(IN_NULL, 1);
        prop.is_struct = true;
        prop.struct_members = 1;
        let layout = EventLayout {
            properties: vec![prop.clone()],
            top_level_count: 1,
        };
        let value = read_value(
            std::ptr::null(),
            &layout,
            &layout.properties[0],
            &[],
            8,
            MAX_STRUCT_DEPTH,
        );
        assert!(value.is_none());
    }

    #[test]
    fn test_read_unsigned_widths() {
        assert_eq!(read_unsigned(&[7]), Some(7));
        assert_eq!(read_unsigned(&2u16.to_le_bytes()), Some(2));
        assert_eq!(read_unsigned(&9u32.to_le_bytes()), Some(9));
        assert_eq!(read_unsigned(&5u64.to_le_bytes()), Some(5));
        assert_eq!(read_unsigned(&[1, 2, 3]), None);
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
