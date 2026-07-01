// Copyright: GMATWiz contributors
// License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

import SwiftUI

@main
struct GMATWizPhoneApp: App {
    init() {
        print("GMATWIZ_IOS hello=\(GmatwizEngine.hello()) build=\(GmatwizEngine.buildhash())")
    }

    var body: some Scene {
        WindowGroup {
            ContentView()
        }
    }
}
