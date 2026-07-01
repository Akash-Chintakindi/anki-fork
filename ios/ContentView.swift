// Copyright: GMATWiz contributors
// License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
//
// SwiftUI review session driven entirely by the SHARED Anki Rust engine
// (via the GMATWiz C FFI). The phone opens the real GMAT::Quant collection,
// fetches the next scheduled card, and records real reviews - no scheduler
// reimplemented in Swift.

import Foundation
import SwiftUI

/// Copies the bundled read-only collection into a writable location once, and
/// exposes review state + answering through the shared engine.
final class ReviewModel: ObservableObject {
    @Published var state: GmatReviewState?
    @Published var status: String = "Opening collection..."
    @Published var revealed = false
    @Published var selected: String?
    @Published var lastCorrect: Bool?
    @Published var scores: GmatScores?
    @Published var syncing = false
    @Published var syncMessage = ""

    // Point these at your self-hosted Anki sync server. From the iOS simulator
    // the host machine's loopback is reachable at 127.0.0.1.
    var syncEndpoint = "http://127.0.0.1:27811/"
    var syncUser = "gmat"
    var syncPass = "wiz"

    private var collection: GmatCollectionHandle?
    private var didSelftestSync = false

    init() { open() }

    func loadScores() {
        guard let c = collection else { return }
        scores = GmatwizEngine.scores(c)
    }

    private func writableCollectionPath() -> String {
        let dir = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
        let dest = dir.appendingPathComponent("gmat.anki2")
        if !FileManager.default.fileExists(atPath: dest.path),
           let src = Bundle.main.url(forResource: "gmat", withExtension: "anki2") {
            try? FileManager.default.copyItem(at: src, to: dest)
        }
        return dest.path
    }

    func open() {
        let path = writableCollectionPath()
        guard let handle = GmatwizEngine.openCollection(path: path) else {
            status = "Failed to open collection"
            return
        }
        collection = handle
        refresh()
        // Headless proof: answer one card so a screenshot shows the queue advance.
        if ProcessInfo.processInfo.arguments.contains("--gmat-selftest"),
           let card = state?.card {
            GmatwizEngine.answer(handle, cardId: card.id, correct: true)
            refresh()
        }
        // Headless proof: run a sync on launch so a screenshot shows the result.
        if ProcessInfo.processInfo.arguments.contains("--gmat-selftest-sync"), !didSelftestSync {
            didSelftestSync = true
            sync(preferUpload: false)
        }
    }

    func refresh() {
        guard let c = collection else { return }
        state = GmatwizEngine.reviewState(c)
        revealed = false
        selected = nil
        lastCorrect = nil
        status = state == nil ? "Failed to read review state" : ""
    }

    func commit() {
        guard let c = collection, let card = state?.card, let choice = selected else { return }
        let correct = choice == card.correct
        lastCorrect = correct
        revealed = true
        // Real review recorded through the shared engine's scheduler.
        GmatwizEngine.answer(c, cardId: card.id, correct: correct)
    }

    func next() { refresh() }

    /// Sync this phone's collection with the desktop via the self-hosted server.
    /// Releases the collection first (SQLite single-writer), syncs on the shared
    /// engine, then reopens and reloads. `preferUpload` picks the direction only
    /// if the server requires a first/divergent full sync.
    func sync(preferUpload: Bool) {
        guard !syncing else { return }
        let path = writableCollectionPath()
        collection = nil  // release the write lock before the engine reopens the file
        syncing = true
        syncMessage = "Syncing…"
        DispatchQueue.global().async {
            let result = GmatwizEngine.sync(
                path: path, endpoint: self.syncEndpoint,
                username: self.syncUser, password: self.syncPass,
                preferUpload: preferUpload)
            DispatchQueue.main.async {
                self.syncing = false
                if let r = result {
                    self.syncMessage = r.ok
                        ? "Synced (\(r.action ?? "ok"))"
                        : "Sync failed: \(r.error ?? "unknown"). Is the sync server running?"
                } else {
                    self.syncMessage = "Sync failed: engine unavailable"
                }
                self.open()
                self.loadScores()
            }
        }
    }
}

struct ContentView: View {
    @StateObject private var model = ReviewModel()
    @State private var tab: Int =
        ProcessInfo.processInfo.arguments.contains("--gmat-tab-readiness") ? 1 : 0

    var body: some View {
        TabView(selection: $tab) {
            ReviewView(model: model)
                .tabItem { Label("Practice", systemImage: "square.and.pencil") }
                .tag(0)
            DashboardView(model: model)
                .tabItem { Label("Readiness", systemImage: "gauge.medium") }
                .tag(1)
        }
    }
}

struct ReviewView: View {
    @ObservedObject var model: ReviewModel

    var body: some View {
        VStack(spacing: 16) {
            Text("GMATWiz")
                .font(.title2).bold()
            Text("running on the shared Anki engine")
                .font(.caption).foregroundStyle(.secondary)

            HStack(spacing: 8) {
                Button("Sync \u{2193}") { model.sync(preferUpload: false) }
                    .buttonStyle(.bordered).disabled(model.syncing)
                Button("Sync \u{2191}") { model.sync(preferUpload: true) }
                    .buttonStyle(.bordered).disabled(model.syncing)
                if !model.syncMessage.isEmpty {
                    Text(model.syncMessage).font(.caption2).foregroundStyle(.secondary)
                }
            }

            if let s = model.state {
                HStack(spacing: 16) {
                    counter("New", s.new)
                    counter("Learn", s.learning)
                    counter("Due", s.review)
                }
                .padding(.vertical, 4)

                if let card = s.card {
                    ScrollView {
                        VStack(alignment: .leading, spacing: 12) {
                            Text(card.topic).font(.caption).foregroundStyle(.secondary)
                            Text(card.stem).font(.headline)
                            ForEach(["A", "B", "C", "D", "E"], id: \.self) { key in
                                if let val = card.options[key], !val.isEmpty {
                                    optionRow(key: key, value: val, card: card)
                                }
                            }
                            if !model.revealed {
                                Button("Commit answer") { model.commit() }
                                    .buttonStyle(.borderedProminent)
                                    .disabled(model.selected == nil)
                            } else {
                                Text(model.lastCorrect == true ? "Correct" : "Not yet")
                                    .bold()
                                    .foregroundStyle(model.lastCorrect == true ? .green : .red)
                                Text(card.explanation).font(.subheadline)
                                Button("Next card") { model.next() }
                                    .buttonStyle(.borderedProminent)
                            }
                        }
                        .padding()
                    }
                } else {
                    Text("Caught up - no cards due.").padding()
                }
            } else {
                Text(model.status).foregroundStyle(.secondary)
            }
            Spacer()
        }
        .padding()
    }

    private func counter(_ label: String, _ n: Int) -> some View {
        VStack {
            Text("\(n)").font(.title3).monospacedDigit().bold()
            Text(label).font(.caption2).foregroundStyle(.secondary)
        }
    }

    private func optionRow(key: String, value: String, card: GmatCard) -> some View {
        let isSelected = model.selected == key
        let isCorrect = card.correct == key
        var bg: Color = Color(.secondarySystemBackground)
        if model.revealed {
            if isCorrect { bg = .green.opacity(0.25) }
            else if isSelected { bg = .red.opacity(0.25) }
        } else if isSelected {
            bg = .accentColor.opacity(0.25)
        }
        return Button(action: { if !model.revealed { model.selected = key } }) {
            HStack {
                Text(key).bold().frame(width: 24)
                Text(value)
                Spacer()
            }
            .padding(10)
            .background(bg)
            .clipShape(RoundedRectangle(cornerRadius: 8))
        }
        .buttonStyle(.plain)
        .disabled(model.revealed)
    }
}

struct DashboardView: View {
    @ObservedObject var model: ReviewModel

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 14) {
                Text("Readiness").font(.title2).bold()
                Text("Three separate questions - each with a range, or an honest \"not enough data.\"")
                    .font(.caption).foregroundStyle(.secondary)

                if let s = model.scores {
                    card(title: "Memory", question: "Can you recall a fact right now?") {
                        if s.memory.status == "shown" {
                            reading("\(s.memory.point ?? 0)%",
                                    "range \(s.memory.low ?? 0)-\(s.memory.high ?? 0)% \u{00b7} \(s.memory.reviews) reviews")
                            if let ece = s.memory.ece, let cal = s.memory.calibrated {
                                Text("\(cal ? "calibrated" : "drift") \u{00b7} ECE \(String(format: "%.3f", ece))")
                                    .font(.caption).foregroundStyle(cal ? .green : .orange)
                            }
                        } else {
                            abstain(s.memory.reason ?? "Not enough data")
                        }
                    }
                    card(title: "Performance", question: "Can you answer a new exam-style question?") {
                        if s.performance.status == "shown" {
                            reading("\(s.performance.point ?? 0)%",
                                    "range \(s.performance.low ?? 0)-\(s.performance.high ?? 0)% \u{00b7} \(s.performance.attempts) new-question attempts")
                            if let e = s.performance.eval {
                                Text("held-out: model \(String(format: "%.3f", e.model_brier)) vs baseline \(String(format: "%.3f", e.baseline_brier)) - \(e.beats_baseline ? "beats baseline" : "not yet beating baseline")")
                                    .font(.caption2).foregroundStyle(.secondary)
                            }
                        } else {
                            abstain(s.performance.reason ?? "Not enough data")
                        }
                    }
                    card(title: "Readiness", question: "What score would you get today?") {
                        if s.readiness.status == "shown" {
                            reading("Q\(s.readiness.point ?? 0)",
                                    "range Q\(s.readiness.low ?? 0)-Q\(s.readiness.high ?? 0) \u{00b7} \(s.readiness.confidence ?? "") confidence")
                            if let m = s.readiness.method {
                                Text(m).font(.caption2).foregroundStyle(.secondary)
                            }
                            if let t = s.readiness.total_reason {
                                Text("Total: \(t)").font(.caption2).foregroundStyle(.secondary)
                            }
                        } else {
                            abstain(s.readiness.reason ?? "Not enough data")
                            if let unmet = s.readiness.unmet {
                                ForEach(unmet, id: \.self) { u in
                                    Text("- \(u)").font(.caption2).foregroundStyle(.secondary)
                                }
                            }
                        }
                    }
                    Text("Coverage: \(s.topics_covered)/\(s.topics_total) Quant topics")
                        .font(.caption).foregroundStyle(.secondary)
                } else {
                    Text("Loading scores...").foregroundStyle(.secondary)
                }
            }
            .padding()
        }
        .onAppear { model.loadScores() }
    }

    private func card<Content: View>(title: String, question: String,
                                     @ViewBuilder content: () -> Content) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(title.uppercased()).font(.caption2).foregroundStyle(.secondary)
            Text(question).font(.subheadline).bold()
            content()
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding()
        .background(Color(.secondarySystemBackground))
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }

    private func reading(_ big: String, _ sub: String) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(big).font(.system(size: 34, weight: .bold, design: .monospaced))
            Text(sub).font(.caption).foregroundStyle(.secondary)
        }
    }

    private func abstain(_ text: String) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            Text("- \u{00b7} -").font(.system(.title3, design: .monospaced)).foregroundStyle(.secondary)
            Text("Not enough data").font(.subheadline).bold().foregroundStyle(.secondary)
            Text(text).font(.caption).foregroundStyle(.secondary)
        }
    }
}
