// Copyright: GMATWiz contributors
// License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
//
// Tiny loopback HTTP/1.1 server (Apple Network framework, no dependencies) that
// serves the bundled SvelteKit "GMATWiz" SPA to an in-app WKWebView and proxies
// its `/_anki/<method>` POSTs to the shared Rust engine.
//
// Why a loopback server instead of a WKURLSchemeHandler: the SvelteKit app uses
// root-absolute URLs (`/gmat`, `/_app/...`) and posts to `/_anki/<method>` with a
// request BODY. WKURLSchemeHandler does not deliver POST bodies, so we mirror the
// desktop's `qt/aqt/mediasrv.py` on 127.0.0.1 instead, where bodies and absolute
// paths work unchanged. Routing here matches mediasrv:
//   GET  /_app/...        -> bundled file under web/sveltekit/_app/...
//   GET  /favicon.ico     -> 204
//   GET  <any other path> -> web/sveltekit/index.html (SPA fallback)
//   POST /_anki/<method>  -> gmatwiz_endpoint(collection, method, body, resourceDir)

import Foundation
import Network

final class WebServer {
    /// Dispatches a `/_anki/<method>` POST to the engine. `method` has no
    /// `/_anki/` prefix; `body` is the raw request body (JSON or ""). Returns the
    /// JSON response string (callers map a nil engine result to "{}").
    typealias EndpointHandler = (_ method: String, _ body: String) -> String

    private let webRoot: URL
    private let onEndpoint: EndpointHandler
    // Concurrent so parallel asset requests from the webview don't serialize;
    // the engine handler itself is serialized by the caller.
    private let queue = DispatchQueue(label: "com.gmatwiz.webserver", attributes: .concurrent)
    private var listener: NWListener?

    /// The ephemeral port the listener bound to (0 until `start()` succeeds).
    private(set) var port: UInt16 = 0

    init(webRoot: URL, onEndpoint: @escaping EndpointHandler) {
        self.webRoot = webRoot
        self.onEndpoint = onEndpoint
    }

    /// Starts the server on an ephemeral 127.0.0.1 port and returns it. Blocks
    /// briefly (<=5s) until the listener is ready so the URL can be built.
    @discardableResult
    func start() throws -> UInt16 {
        let params = NWParameters.tcp
        params.allowLocalEndpointReuse = true
        // Bind loopback only (no LAN exposure, and 127.0.0.1 is exempt from the
        // iOS Local Network privacy prompt). `.any` => kernel-assigned port.
        params.requiredLocalEndpoint = .hostPort(host: "127.0.0.1", port: .any)

        let listener = try NWListener(using: params)
        self.listener = listener

        let ready = DispatchSemaphore(value: 0)
        listener.stateUpdateHandler = { state in
            switch state {
            case .ready, .failed, .cancelled:
                ready.signal()
            default:
                break
            }
        }
        listener.newConnectionHandler = { [weak self] connection in
            self?.accept(connection)
        }
        listener.start(queue: queue)

        _ = ready.wait(timeout: .now() + 5)
        port = listener.port?.rawValue ?? 0
        return port
    }

    func stop() {
        listener?.cancel()
        listener = nil
    }

    // MARK: - Connection handling

    private func accept(_ connection: NWConnection) {
        connection.start(queue: queue)
        receive(connection, buffer: Data())
    }

    /// Reads until a full request (headers + Content-Length body) is buffered,
    /// then responds. One request per connection (we reply `Connection: close`).
    private func receive(_ connection: NWConnection, buffer: Data) {
        connection.receive(minimumIncompleteLength: 1, maximumLength: 65536) {
            [weak self] chunk, _, isComplete, error in
            guard let self else { connection.cancel(); return }

            var buffer = buffer
            if let chunk { buffer.append(chunk) }

            if let request = HTTPRequest(buffer),
               buffer.count >= request.bodyStart + request.contentLength {
                let body = buffer.subdata(in: request.bodyStart ..< request.bodyStart + request.contentLength)
                self.respond(connection, request: request, body: body)
                return
            }

            if error != nil || isComplete {
                connection.cancel()
                return
            }
            self.receive(connection, buffer: buffer)
        }
    }

    private func respond(_ connection: NWConnection, request: HTTPRequest, body: Data) {
        let response = route(request, body: body)
        var head = "HTTP/1.1 \(response.status) \(reason(response.status))\r\n"
        head += "Content-Type: \(response.contentType)\r\n"
        head += "Content-Length: \(response.body.count)\r\n"
        head += "Connection: close\r\n"
        for (key, value) in response.headers {
            head += "\(key): \(value)\r\n"
        }
        head += "\r\n"

        var out = Data(head.utf8)
        if request.method != "HEAD" {
            out.append(response.body)
        }
        connection.send(content: out, completion: .contentProcessed { _ in
            connection.cancel()
        })
    }

    // MARK: - Routing (mirrors qt/aqt/mediasrv.py)

    private struct HTTPResponse {
        var status: Int
        var contentType: String
        var body: Data
        var headers: [String: String] = [:]
    }

    private func route(_ request: HTTPRequest, body: Data) -> HTTPResponse {
        var path = request.path
        if let q = path.firstIndex(of: "?") { path = String(path[..<q]) }

        // Our GMATWiz endpoints return JSON: POST /_anki/gmat<...>
        if request.method == "POST", path.hasPrefix("/_anki/gmat") {
            let method = String(path.dropFirst("/_anki/".count))
            let bodyString = String(data: body, encoding: .utf8) ?? ""
            let json = onEndpoint(method, bodyString)
            return HTTPResponse(status: 200, contentType: "application/json", body: Data(json.utf8))
        }

        // The SvelteKit runtime fetches translations on boot: i18nResources returns
        // a generic.Json protobuf whose `json` field the client JSON.parses. Return
        // a valid minimal payload so boot succeeds with no translations (our UI uses
        // literal strings, not i18n keys). generic.Json { bytes json = 1 } → tag
        // 0x0A (field 1, wire type 2) + length + payload.
        if path == "/_anki/i18nResources" {
            // One empty en-US Fluent bundle: enough that the i18n runtime has a
            // bundle (it dereferences bundles[0]) while carrying no messages.
            let payload = Data(#"{"resources":{"en":""},"langs":{"en":"en-US"}}"#.utf8)
            var proto = Data([0x0A])
            proto.append(varint(UInt64(payload.count)))
            proto.append(payload)
            return HTTPResponse(status: 200, contentType: "application/binary", body: proto)
        }

        // Any other non-gmat protobuf backend call: empty message (decodes cleanly).
        if path.hasPrefix("/_anki/") {
            return HTTPResponse(status: 200, contentType: "application/binary", body: Data())
        }

        guard request.method == "GET" || request.method == "HEAD" else {
            return HTTPResponse(status: 405, contentType: "text/plain", body: Data("Method not allowed".utf8))
        }

        if path == "/favicon.ico" {
            return HTTPResponse(status: 204, contentType: "text/plain", body: Data())
        }

        // Immutable assets: serve the exact bundled file. Everything else is an
        // SPA route -> index.html (client-side router takes over).
        if path.hasPrefix("/_app/") {
            let fileURL = safeChild(of: webRoot, relative: String(path.dropFirst()))
            if let fileURL, let data = try? Data(contentsOf: fileURL) {
                var headers: [String: String] = [:]
                if path.contains("/immutable/") {
                    headers["Cache-Control"] = "max-age=31536000, immutable"
                }
                return HTTPResponse(
                    status: 200,
                    contentType: mimeType(forExtension: fileURL.pathExtension),
                    body: data,
                    headers: headers)
            }
            return HTTPResponse(status: 404, contentType: "text/plain", body: Data("Not found: \(path)".utf8))
        }

        if let data = try? Data(contentsOf: webRoot.appendingPathComponent("index.html")) {
            return HTTPResponse(status: 200, contentType: "text/html", body: data)
        }
        return HTTPResponse(status: 404, contentType: "text/plain", body: Data("index.html missing".utf8))
    }

    /// Resolves `relative` under `base`, rejecting path traversal outside `base`.
    private func safeChild(of base: URL, relative: String) -> URL? {
        let resolved = base.appendingPathComponent(relative).standardizedFileURL
        let root = base.standardizedFileURL.path
        return resolved.path.hasPrefix(root) ? resolved : nil
    }

    private func mimeType(forExtension ext: String) -> String {
        switch ext.lowercased() {
        case "html", "htm": return "text/html"
        case "css": return "text/css"
        case "js", "mjs": return "text/javascript"
        case "json", "map": return "application/json"
        case "svg": return "image/svg+xml"
        case "png": return "image/png"
        case "jpg", "jpeg": return "image/jpeg"
        case "gif": return "image/gif"
        case "ico": return "image/x-icon"
        case "webp": return "image/webp"
        case "woff2": return "font/woff2"
        case "woff": return "font/woff"
        case "ttf": return "font/ttf"
        case "wasm": return "application/wasm"
        case "txt": return "text/plain"
        default: return "application/octet-stream"
        }
    }

    /// Protobuf base-128 varint (little-endian groups) for a length prefix.
    private func varint(_ value: UInt64) -> Data {
        var v = value
        var out = Data()
        repeat {
            var byte = UInt8(v & 0x7F)
            v >>= 7
            if v != 0 { byte |= 0x80 }
            out.append(byte)
        } while v != 0
        return out
    }

    private func reason(_ status: Int) -> String {
        switch status {
        case 200: return "OK"
        case 204: return "No Content"
        case 404: return "Not Found"
        case 405: return "Method Not Allowed"
        case 500: return "Internal Server Error"
        default: return "OK"
        }
    }
}

/// Minimal parse of an HTTP request head: method, path, Content-Length, and the
/// byte offset where the body begins. Returns nil until the full header block
/// (terminated by CRLFCRLF) has been received.
private struct HTTPRequest {
    let method: String
    let path: String
    let contentLength: Int
    let bodyStart: Int

    init?(_ buffer: Data) {
        let terminator = Data([13, 10, 13, 10]) // \r\n\r\n
        guard let range = buffer.range(of: terminator) else { return nil }
        let headerData = buffer.subdata(in: buffer.startIndex ..< range.lowerBound)
        guard let header = String(data: headerData, encoding: .utf8) else { return nil }

        let lines = header.components(separatedBy: "\r\n")
        let requestLine = lines.first?.split(separator: " ") ?? []
        guard requestLine.count >= 2 else { return nil }

        method = String(requestLine[0])
        path = String(requestLine[1])
        bodyStart = range.upperBound

        var length = 0
        for line in lines.dropFirst() where line.lowercased().hasPrefix("content-length:") {
            let value = line.drop(while: { $0 != ":" }).dropFirst()
            length = Int(value.trimmingCharacters(in: .whitespaces)) ?? 0
        }
        contentLength = length
    }
}
