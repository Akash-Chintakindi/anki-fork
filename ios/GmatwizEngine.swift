// Copyright: GMATWiz contributors
// License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
//
// Swift wrapper over the shared Anki Rust engine via the GMATWiz C FFI.
// The phone app calls the SAME scheduler as the desktop app; nothing is
// reimplemented in Swift. Link against GmatwizFFI.xcframework (see build-ios.sh).

import Foundation
import GmatwizFFI

/// Opaque handle to a shared-engine backend instance.
final class GmatwizBackendHandle {
    fileprivate let ptr: OpaquePointer
    fileprivate init(_ ptr: OpaquePointer) { self.ptr = ptr }
    deinit { gmatwiz_backend_free(ptr) }
}

/// Opaque handle to an open collection (the shared engine + a real .anki2 DB).
final class GmatCollectionHandle {
    fileprivate let ptr: OpaquePointer
    fileprivate init(_ ptr: OpaquePointer) { self.ptr = ptr }
    deinit { gmatwiz_collection_free(ptr) }
}

/// A scheduled card decoded from the engine's JSON.
struct GmatCard: Decodable {
    let id: Int64
    let stem: String
    let options: [String: String]
    let correct: String
    let explanation: String
    let topic: String
}

/// Review state returned by the shared scheduler.
struct GmatReviewState: Decodable {
    let new: Int
    let learning: Int
    let review: Int
    let card: GmatCard?
}

enum GmatwizEngine {
    /// Smoke-test greeting proving the engine is linked.
    static func hello() -> String {
        guard let c = gmatwiz_hello() else { return "(null)" }
        defer { gmatwiz_string_free(c) }
        return String(cString: c)
    }

    /// Engine build hash (should match the desktop build).
    static func buildhash() -> String {
        guard let c = gmatwiz_buildhash() else { return "(null)" }
        defer { gmatwiz_string_free(c) }
        return String(cString: c)
    }

    /// Open a backend from a protobuf-encoded BackendInit message.
    static func openBackend(init initBytes: [UInt8]) -> GmatwizBackendHandle? {
        let ptr = initBytes.withUnsafeBufferPointer { buf in
            gmatwiz_backend_open(buf.baseAddress, buf.count)
        }
        guard let ptr else { return nil }
        return GmatwizBackendHandle(ptr)
    }

    /// Run a protobuf service method against the shared engine.
    /// Returns the status code (0 ok, 1 backend error) and the response bytes.
    static func command(
        _ backend: GmatwizBackendHandle,
        service: UInt32,
        method: UInt32,
        input: [UInt8]
    ) -> (code: Int32, output: [UInt8]) {
        var outPtr: UnsafeMutablePointer<UInt8>? = nil
        var outLen: Int = 0
        let code = input.withUnsafeBufferPointer { buf in
            gmatwiz_backend_command(backend.ptr, service, method, buf.baseAddress, buf.count, &outPtr, &outLen)
        }
        var out = [UInt8]()
        if let p = outPtr, outLen > 0 {
            out = Array(UnsafeBufferPointer(start: p, count: outLen))
            gmatwiz_buffer_free(p, outLen)
        }
        return (code, out)
    }

    // --- High-level collection review API (shared engine) ---

    /// Open a collection at the given .anki2 path.
    static func openCollection(path: String) -> GmatCollectionHandle? {
        guard let ptr = gmatwiz_open_collection(path) else { return nil }
        return GmatCollectionHandle(ptr)
    }

    /// Current review state for the deck (counts + next card), via the scheduler.
    static func reviewState(
        _ collection: GmatCollectionHandle,
        deck: String = "GMAT::Quant"
    ) -> GmatReviewState? {
        guard let c = gmatwiz_collection_state(collection.ptr, deck) else { return nil }
        defer { gmatwiz_string_free(c) }
        let json = String(cString: c)
        guard let data = json.data(using: .utf8) else { return nil }
        return try? JSONDecoder().decode(GmatReviewState.self, from: data)
    }

    /// Answer the current card through the real scheduler (records a review).
    @discardableResult
    static func answer(
        _ collection: GmatCollectionHandle,
        cardId: Int64,
        correct: Bool
    ) -> Bool {
        return gmatwiz_collection_answer(collection.ptr, cardId, correct) == 0
    }
}
