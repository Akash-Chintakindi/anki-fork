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

// --- Dashboard scores (Memory / Performance / Readiness), computed in-engine ---

struct CalibrationBin: Decodable {
    let label: String
    let observed: Double
    let n: Int
}

struct MemoryScore: Decodable {
    let status: String
    let point: Int?
    let low: Int?
    let high: Int?
    let reviews: Int
    let reviews_required: Int?
    let reason: String?
    let target: Int?
    let ece: Double?
    let calibrated: Bool?
    let bins: [CalibrationBin]?
}

struct PerfEval: Decodable {
    let baseline_brier: Double
    let model_brier: Double
    let beats_baseline: Bool
    let test_n: Int
}

struct WeakTopic: Decodable {
    let topic: String
    let accuracy: Double
    let n: Int
}

struct TimingInfo: Decodable {
    let n: Int
    let avg_ms: Int
    let target_ms: Int
    let rushed_wrong: Int
    let slow_correct: Int
}

struct PerformanceScore: Decodable {
    let status: String
    let point: Int?
    let low: Int?
    let high: Int?
    let attempts: Int
    let attempts_required: Int?
    let reason: String?
    let weak_topics: [WeakTopic]?
    let eval: PerfEval?
    let timing: TimingInfo?
}

struct MockEntry: Decodable {
    let ts: Int
    let accuracy: Double
    let n: Int
    let q: Int
}

struct Calibration: Decodable {
    let n: Int
    let bias: Double
    let residual: Double
    let point: Int
    let low: Int
    let high: Int
}

struct ReadinessScore: Decodable {
    let status: String
    let section: String?
    let point: Int?
    let low: Int?
    let high: Int?
    let scale: String?
    let confidence: String?
    let method: String?
    let total_reason: String?
    let unmet: [String]?
    let reason: String?
    let mocks: [MockEntry]?
    let mock_gap: Int?
    let calibration: Calibration?
}

struct GmatScores: Decodable {
    let memory: MemoryScore
    let performance: PerformanceScore
    let readiness: ReadinessScore
    let topics_covered: Int
    let topics_total: Int
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

    /// Answer the current card through the real scheduler (records a review
    /// with the real time taken, feeding the timing analytics).
    @discardableResult
    static func answer(
        _ collection: GmatCollectionHandle,
        cardId: Int64,
        correct: Bool,
        ms: UInt32 = 1500
    ) -> Bool {
        return gmatwiz_collection_answer(collection.ptr, cardId, correct, ms) == 0
    }

    /// The three honest scores computed in the shared engine (same logic as desktop).
    static func scores(_ collection: GmatCollectionHandle) -> GmatScores? {
        guard let c = gmatwiz_collection_scores(collection.ptr) else { return nil }
        defer { gmatwiz_string_free(c) }
        guard let data = String(cString: c).data(using: .utf8) else { return nil }
        return try? JSONDecoder().decode(GmatScores.self, from: data)
    }

    /// Dispatch a GMATWiz web endpoint (e.g. "gmatOverview", "gmatToday") against
    /// the open collection, so the embedded SvelteKit app drives every feature
    /// through the same engine the desktop uses. `name` has no `/_anki/` prefix,
    /// `body` is the POST body (JSON or ""), and `resourceDir` is the bundled
    /// gmatwiz/ folder (lessons/ + content/). Returns the JSON response, or nil.
    static func endpoint(
        _ collection: GmatCollectionHandle,
        name: String,
        body: String,
        resourceDir: String
    ) -> String? {
        guard let c = gmatwiz_endpoint(collection.ptr, name, body, resourceDir) else { return nil }
        defer { gmatwiz_string_free(c) }
        return String(cString: c)
    }

    /// Sync the collection at `path` against a self-hosted Anki sync server so the
    /// phone shares ONE collection with the desktop. The caller must release any
    /// open collection handle for this path first (SQLite is single-writer).
    static func sync(
        path: String,
        endpoint: String,
        username: String,
        password: String,
        preferUpload: Bool
    ) -> GmatSyncResult? {
        guard let c = gmatwiz_sync(path, endpoint, username, password, preferUpload) else {
            return nil
        }
        defer { gmatwiz_string_free(c) }
        guard let data = String(cString: c).data(using: .utf8) else { return nil }
        return try? JSONDecoder().decode(GmatSyncResult.self, from: data)
    }
}

/// Result of a sync attempt from the shared engine. On failure `error` says why
/// (honesty rule: never a bare "failed").
struct GmatSyncResult: Decodable {
    let ok: Bool
    let action: String?
    let error: String?
}
