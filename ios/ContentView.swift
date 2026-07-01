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

    private var collection: GmatCollectionHandle?

    init() { open() }

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
}

struct ContentView: View {
    @StateObject private var model = ReviewModel()

    var body: some View {
        VStack(spacing: 16) {
            Text("GMATWiz")
                .font(.title2).bold()
            Text("running on the shared Anki engine")
                .font(.caption).foregroundStyle(.secondary)

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
