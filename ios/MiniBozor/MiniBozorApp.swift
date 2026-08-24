import SwiftUI

@main
struct MiniBozorApp: App {
    @State var session = AppSession()

    var body: some Scene {
        WindowGroup {
            RootView()
                .environment(session)
                .environment(CartRepository.shared)
                .preferredColorScheme(.light)
        }
    }
}
