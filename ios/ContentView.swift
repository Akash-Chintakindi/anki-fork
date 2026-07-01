// Copyright: GMATWiz contributors
// License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
//
// Minimal SwiftUI demo proving the iOS app talks to the shared Anki engine.
// Drop this into an Xcode app target that links GmatwizFFI.xcframework and
// includes GmatwizEngine.swift.

import SwiftUI

struct ContentView: View {
    var body: some View {
        VStack(spacing: 12) {
            Text("GMATWiz engine on iOS")
                .font(.headline)
            Text(GmatwizEngine.hello())
            Text("build: \(GmatwizEngine.buildhash())")
                .font(.footnote)
                .foregroundStyle(.secondary)
        }
        .padding()
    }
}
