import SwiftUI

/// Main content view with tab-based navigation.
struct ContentView: View {
    @State private var selectedTab = 0

    var body: some View {
        TabView(selection: $selectedTab) {
            MapContainerView()
                .tabItem {
                    Label("Map", systemImage: "map.fill")
                }
                .tag(0)

            CallListView()
                .tabItem {
                    Label("List", systemImage: "list.bullet")
                }
                .tag(1)

            ArchiveView()
                .tabItem {
                    Label("Archive", systemImage: "clock.arrow.circlepath")
                }
                .tag(2)

            SettingsView()
                .tabItem {
                    Label("Settings", systemImage: "gear")
                }
                .tag(3)
        }
    }
}

#Preview {
    ContentView()
}
