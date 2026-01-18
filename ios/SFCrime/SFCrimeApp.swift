import SwiftUI
import SwiftData

/// Main entry point for the SFCrime iOS app.
/// A Citizen-style live crime map for San Francisco.
@main
struct SFCrimeApp: App {
    /// SwiftData model container for local caching
    var sharedModelContainer: ModelContainer = {
        let schema = Schema([
            CachedDispatchCall.self,
            CachedIncidentReport.self,
        ])
        let modelConfiguration = ModelConfiguration(
            schema: schema,
            isStoredInMemoryOnly: false
        )

        do {
            return try ModelContainer(for: schema, configurations: [modelConfiguration])
        } catch {
            fatalError("Could not create ModelContainer: \(error)")
        }
    }()

    var body: some Scene {
        WindowGroup {
            ContentView()
        }
        .modelContainer(sharedModelContainer)
    }
}
