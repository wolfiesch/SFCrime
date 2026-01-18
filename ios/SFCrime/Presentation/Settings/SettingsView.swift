import SwiftUI

/// Settings view for app configuration.
struct SettingsView: View {
    @StateObject private var viewModel = SettingsViewModel()
    @State private var showingClearCacheAlert = false

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
                        Text("Cache Size")
                        Spacer()
                        Text(viewModel.cacheSize)
                            .foregroundColor(.secondary)
                    }

                    Button(role: .destructive) {
                        showingClearCacheAlert = true
                    } label: {
                        Text("Clear Cache")
                    }
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
                    viewModel.clearCache()
                }
            } message: {
                Text("This will remove all cached data. The app will re-download data when needed.")
            }
            .task {
                await viewModel.checkHealth()
            }
        }
    }
}

// MARK: - View Model

@MainActor
class SettingsViewModel: ObservableObject {
    @Published var health: HealthResponse?
    @Published var isLoading = false
    @Published var cacheSize = "Calculating..."

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

    func clearCache() {
        // Clear SwiftData cache
        // In a real implementation, this would delete cached records
        cacheSize = "0 KB"
    }

    func calculateCacheSize() {
        // Calculate SwiftData database size
        // In a real implementation, this would check the database file size
        cacheSize = "2.4 MB"
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
