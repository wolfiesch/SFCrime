import SwiftUI
import SwiftData

/// Settings view for app configuration.
struct SettingsView: View {
    @Environment(\.modelContext) private var modelContext
    @StateObject private var viewModel = SettingsViewModel()
    @State private var showingClearCacheAlert = false
    @State private var cacheSize: String = "Calculating..."
    @State private var cachedCallsCount: Int = 0
    @State private var cachedIncidentsCount: Int = 0

    var body: some View {
        NavigationStack {
            Form {
                // API Status
                Section("Data Status") {
                    if let health = viewModel.health {
                        HStack {
                            Text("API Status")
                            Spacer()
                            Text(health.status.capitalized)
                                .foregroundColor(.green)
                        }

                        if let dispatchSync = health.dispatchCalls.lastSync {
                            HStack {
                                Text("Dispatch Calls")
                                Spacer()
                                VStack(alignment: .trailing) {
                                    Text("\(health.dispatchCalls.recordCount) records")
                                        .font(.subheadline)
                                    Text("Last sync: \(dispatchSync, style: .relative) ago")
                                        .font(.caption)
                                        .foregroundColor(.secondary)
                                }
                            }
                        }

                        if let incidentSync = health.incidentReports.lastSync {
                            HStack {
                                Text("Incident Reports")
                                Spacer()
                                VStack(alignment: .trailing) {
                                    Text("\(health.incidentReports.recordCount) records")
                                        .font(.subheadline)
                                    if let range = health.incidentReports.dateRange,
                                       range.count == 2 {
                                        Text("\(range[0]) to \(range[1])")
                                            .font(.caption)
                                            .foregroundColor(.secondary)
                                    }
                                }
                            }
                        }
                    } else if viewModel.isLoading {
                        HStack {
                            Text("Loading status...")
                            Spacer()
                            ProgressView()
                        }
                    } else {
                        HStack {
                            Text("API Status")
                            Spacer()
                            Text("Unable to connect")
                                .foregroundColor(.red)
                        }
                    }

                    Button("Refresh Status") {
                        Task {
                            await viewModel.checkHealth()
                        }
                    }
                }

                // Cache Management
                Section("Storage") {
                    HStack {
                        Text("Cached Calls")
                        Spacer()
                        Text("\(cachedCallsCount)")
                            .foregroundColor(.secondary)
                    }

                    HStack {
                        Text("Cached Incidents")
                        Spacer()
                        Text("\(cachedIncidentsCount)")
                            .foregroundColor(.secondary)
                    }

                    HStack {
                        Text("Database Size")
                        Spacer()
                        Text(cacheSize)
                            .foregroundColor(.secondary)
                    }

                    Button(role: .destructive) {
                        showingClearCacheAlert = true
                    } label: {
                        Text("Clear Cache")
                    }
                    .disabled(cachedCallsCount == 0 && cachedIncidentsCount == 0)
                }

                // About
                Section("About") {
                    HStack {
                        Text("Version")
                        Spacer()
                        Text("1.0.0")
                            .foregroundColor(.secondary)
                    }

                    Link(destination: URL(string: "https://datasf.org")!) {
                        HStack {
                            Text("Data Source")
                            Spacer()
                            Text("DataSF Open Data")
                                .foregroundColor(.secondary)
                            Image(systemName: "arrow.up.right")
                                .font(.caption)
                        }
                    }
                    .foregroundColor(.primary)

                    Link(destination: URL(string: "https://github.com")!) {
                        HStack {
                            Text("Source Code")
                            Spacer()
                            Text("GitHub")
                                .foregroundColor(.secondary)
                            Image(systemName: "arrow.up.right")
                                .font(.caption)
                        }
                    }
                    .foregroundColor(.primary)
                }

                // Legal
                Section("Legal") {
                    NavigationLink("Privacy Policy") {
                        PrivacyPolicyView()
                    }

                    NavigationLink("Terms of Service") {
                        TermsOfServiceView()
                    }

                    NavigationLink("Data Attribution") {
                        DataAttributionView()
                    }
                }
            }
            .navigationTitle("Settings")
            .alert("Clear Cache?", isPresented: $showingClearCacheAlert) {
                Button("Cancel", role: .cancel) { }
                Button("Clear", role: .destructive) {
                    clearCache()
                }
            } message: {
                Text("This will remove all cached data. The app will re-download data when needed.")
            }
            .task {
                await viewModel.checkHealth()
                await updateCacheStats()
            }
        }
    }

    // MARK: - Cache Management

    /// Update cache statistics from SwiftData
    private func updateCacheStats() async {
        // Count cached records
        let callsDescriptor = FetchDescriptor<CachedDispatchCall>()
        let incidentsDescriptor = FetchDescriptor<CachedIncidentReport>()

        do {
            cachedCallsCount = try modelContext.fetchCount(callsDescriptor)
            cachedIncidentsCount = try modelContext.fetchCount(incidentsDescriptor)
        } catch {
            print("Error counting cache: \(error)")
            cachedCallsCount = 0
            cachedIncidentsCount = 0
        }

        // Calculate database file size
        cacheSize = calculateDatabaseSize()
    }

    /// Clear all cached data from SwiftData
    private func clearCache() {
        do {
            try modelContext.delete(model: CachedDispatchCall.self)
            try modelContext.delete(model: CachedIncidentReport.self)
            try modelContext.save()

            // Update stats
            cachedCallsCount = 0
            cachedIncidentsCount = 0

            // Recalculate size (may need delay for file system)
            Task {
                try? await Task.sleep(for: .milliseconds(500))
                cacheSize = calculateDatabaseSize()
            }
        } catch {
            print("Error clearing cache: \(error)")
        }
    }

    /// Calculate the SwiftData database file size
    private func calculateDatabaseSize() -> String {
        // Get the default SwiftData store location
        let fileManager = FileManager.default
        guard let appSupport = fileManager.urls(for: .applicationSupportDirectory, in: .userDomainMask).first else {
            return "Unknown"
        }

        // SwiftData stores in default.store by default
        let storeURL = appSupport.appendingPathComponent("default.store")

        // Sum up all files in the store directory
        var totalSize: Int64 = 0

        if let enumerator = fileManager.enumerator(at: storeURL, includingPropertiesForKeys: [.fileSizeKey]) {
            for case let fileURL as URL in enumerator {
                if let fileSize = try? fileURL.resourceValues(forKeys: [.fileSizeKey]).fileSize {
                    totalSize += Int64(fileSize)
                }
            }
        }

        // Format as human-readable size
        return ByteCountFormatter.string(fromByteCount: totalSize, countStyle: .file)
    }
}

// MARK: - View Model

@MainActor
class SettingsViewModel: ObservableObject {
    @Published var health: HealthResponse?
    @Published var isLoading = false

    private let apiClient = APIClient.shared

    func checkHealth() async {
        isLoading = true
        defer { isLoading = false }

        do {
            health = try await apiClient.checkHealth()
        } catch {
            health = nil
            print("Error checking health: \(error)")
        }
    }
}

// MARK: - Legal Views

struct PrivacyPolicyView: View {
    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                Text("Privacy Policy")
                    .font(.title.bold())

                Text("Last updated: January 2026")
                    .foregroundColor(.secondary)

                Text("""
                SFCrime is a crime awareness app that displays publicly available data from DataSF.

                **Data Collection**
                - We do not collect personal information
                - Location data is used only to show nearby incidents and is not stored
                - No data is shared with third parties

                **Data Sources**
                - All crime data comes from DataSF Open Data Portal
                - Data is publicly available at data.sfgov.org

                **Contact**
                For privacy concerns, please contact us at privacy@sfcrime.app
                """)
            }
            .padding()
        }
        .navigationTitle("Privacy Policy")
        .navigationBarTitleDisplayMode(.inline)
    }
}

struct TermsOfServiceView: View {
    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                Text("Terms of Service")
                    .font(.title.bold())

                Text("Last updated: January 2026")
                    .foregroundColor(.secondary)

                Text("""
                By using SFCrime, you agree to these terms.

                **Disclaimer**
                - Crime data is provided for informational purposes only
                - Data may be delayed, incomplete, or contain errors
                - Do not rely solely on this app for personal safety decisions

                **Acceptable Use**
                - Use this app responsibly
                - Do not use for illegal purposes
                - Do not harass or stalk individuals

                **Limitations**
                - We are not responsible for actions taken based on app data
                - Service availability is not guaranteed
                """)
            }
            .padding()
        }
        .navigationTitle("Terms of Service")
        .navigationBarTitleDisplayMode(.inline)
    }
}

struct DataAttributionView: View {
    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                Text("Data Attribution")
                    .font(.title.bold())

                Text("""
                **Data Sources**

                All crime and incident data displayed in this app is sourced from:

                **City and County of San Francisco**
                DataSF Open Data Portal
                https://data.sfgov.org

                **Datasets Used:**
                - Police Department Incident Reports (2018 to Present)
                - Police Calls for Service

                **License:**
                Data is provided under the Open Data Commons Public Domain Dedication and License (PDDL).

                **Disclaimer:**
                This app is not affiliated with or endorsed by the City and County of San Francisco or the San Francisco Police Department.
                """)
            }
            .padding()
        }
        .navigationTitle("Data Attribution")
        .navigationBarTitleDisplayMode(.inline)
    }
}

#Preview {
    SettingsView()
}
