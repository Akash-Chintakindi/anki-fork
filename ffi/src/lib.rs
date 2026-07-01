// Copyright: GMATWiz contributors
// License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

//! GMATWiz C FFI over the shared Anki Rust engine.
//!
//! This exposes a minimal C ABI so a Swift (iOS) app can drive the SAME Rust
//! backend as the desktop app, using the protobuf `(service, method)` command
//! interface - the same approach Anki-compatible iOS clients use. No scheduling
//! logic is reimplemented here; we only marshal bytes in and out of the engine,
//! so the desktop and phone share one scheduler.

use std::ffi::c_char;
use std::ffi::c_int;
use std::ffi::CString;
use std::ptr;
use std::slice;

use anki::backend::init_backend;
use anki::backend::Backend;

/// Opaque handle to a backend instance, owned by the caller.
pub struct GmatwizBackend {
    inner: Backend,
}

fn to_c_string(s: impl Into<Vec<u8>>) -> *mut c_char {
    match CString::new(s) {
        Ok(c) => c.into_raw(),
        Err(_) => ptr::null_mut(),
    }
}

/// Engine build hash. Free the result with `gmatwiz_string_free`.
#[no_mangle]
pub extern "C" fn gmatwiz_buildhash() -> *mut c_char {
    to_c_string(anki::version::buildhash())
}

/// Smoke-test greeting proving FFI + engine linkage. Free with `gmatwiz_string_free`.
#[no_mangle]
pub extern "C" fn gmatwiz_hello() -> *mut c_char {
    to_c_string("GMATWiz engine online (Rust FFI)")
}

/// Free a string returned by this library.
///
/// # Safety
/// `ptr` must have been returned by one of this library's string functions.
#[no_mangle]
pub unsafe extern "C" fn gmatwiz_string_free(ptr: *mut c_char) {
    if !ptr.is_null() {
        drop(CString::from_raw(ptr));
    }
}

/// Open a backend from a protobuf-encoded `BackendInit` message.
/// Returns null on failure.
///
/// # Safety
/// `init_ptr` must point to `init_len` readable bytes (or be null).
#[no_mangle]
pub unsafe extern "C" fn gmatwiz_backend_open(
    init_ptr: *const u8,
    init_len: usize,
) -> *mut GmatwizBackend {
    if init_ptr.is_null() {
        return ptr::null_mut();
    }
    let init = slice::from_raw_parts(init_ptr, init_len);
    match init_backend(init) {
        Ok(inner) => Box::into_raw(Box::new(GmatwizBackend { inner })),
        Err(_) => ptr::null_mut(),
    }
}

/// Free a backend opened with `gmatwiz_backend_open`.
///
/// # Safety
/// `handle` must have been returned by `gmatwiz_backend_open` (or be null).
#[no_mangle]
pub unsafe extern "C" fn gmatwiz_backend_free(handle: *mut GmatwizBackend) {
    if !handle.is_null() {
        drop(Box::from_raw(handle));
    }
}

/// Run a protobuf service method against the shared engine.
///
/// On success returns 0; on a backend error returns 1. In both cases
/// `*out_ptr` / `*out_len` are set to a newly-allocated buffer (the protobuf
/// response, or the encoded `BackendError`) that the caller MUST free with
/// `gmatwiz_buffer_free`. Returns -1 for invalid arguments.
///
/// # Safety
/// `handle` must be a valid backend; `in_ptr` must point to `in_len` bytes (or
/// be null); `out_ptr` and `out_len` must be valid, writable pointers.
#[no_mangle]
pub unsafe extern "C" fn gmatwiz_backend_command(
    handle: *mut GmatwizBackend,
    service: u32,
    method: u32,
    in_ptr: *const u8,
    in_len: usize,
    out_ptr: *mut *mut u8,
    out_len: *mut usize,
) -> c_int {
    if handle.is_null() || out_ptr.is_null() || out_len.is_null() {
        return -1;
    }
    let backend = &(*handle).inner;
    let input: &[u8] = if in_ptr.is_null() {
        &[]
    } else {
        slice::from_raw_parts(in_ptr, in_len)
    };
    let (code, bytes) = match backend.run_service_method(service, method, input) {
        Ok(out) => (0, out),
        Err(err) => (1, err),
    };
    let mut boxed = bytes.into_boxed_slice();
    *out_ptr = boxed.as_mut_ptr();
    *out_len = boxed.len();
    std::mem::forget(boxed);
    code
}

/// Free a buffer returned by `gmatwiz_backend_command`.
///
/// # Safety
/// `ptr`/`len` must be exactly what a single `gmatwiz_backend_command` call wrote.
#[no_mangle]
pub unsafe extern "C" fn gmatwiz_buffer_free(ptr: *mut u8, len: usize) {
    if !ptr.is_null() && len > 0 {
        drop(Box::from_raw(slice::from_raw_parts_mut(ptr, len)));
    }
}
