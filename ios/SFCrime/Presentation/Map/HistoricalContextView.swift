import SwiftUI
import MapKit

/// View displaying historical context and crime patterns for a location.
/// Shown when user long-presses on the map.
struct HistoricalContextView: View {
    let coordinate: CLLocationCoordinate2D
    let onDismiss: () -> Void

    @StateObject private var viewModel = HistoricalContextViewModel()

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 16) {
                    // Location header
                    locationHeader

                    Divider()

                    // Ambient context (AI-synthesized summary)
                    if let context = viewModel.ambientContext {
                        ambientContextSection(context)
                    }

                    // Crime statistics
                    if !viewModel.crimeStats.isEmpty {
                        crimeStatsSection
                    }

                    // Recent events list
                    if !viewModel.recentEvents.isEmpty {
                        recentEventsSection
                    }

                    // Loading / Empty states
                    if viewModel.isLoading {
                        loadingView
                    } else if viewModel.isEmpty {
                        emptyStateView
                    }
                }
                .padding()
            }
            .navigationTitle("Location History")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Done") { onDismiss() }
                }
            }
            .task {
                await viewModel.loadData(for: coordinate)
            }
        }
    }

    // MARK: - Subviews

    private var locationHeader: some View {
        VStack(alignment: .leading, spacing: 4) {
            if let neighborhood = viewModel.neighborhood {
                Text(neighborhood)
                    .font(.headline)
            }
            Text(String(format: "%.4f, %.4f", coordinate.latitude, coordinate.longitude))
                .font(.caption)
                .foregroundColor(.secondary)
        }
    }

    private func ambientContextSection(_ context: String) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Label("Historical Context", systemImage: "clock.arrow.circlepath")
                .font(.subheadline.bold())
                .foregroundColor(.secondary)

            Text(context)
                .font(.body)
                .foregroundColor(.primary)
                .padding()
                .background(Color(uiColor: .systemGray6))
                .cornerRadius(12)
        }
    }

    private var crimeStatsSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            Label("Crime Patterns (Last 30 Days)", systemImage: "chart.bar.fill")
                .font(.subheadline.bold())
                .foregroundColor(.secondary)

            LazyVGrid(columns: [
                GridItem(.flexible()),
                GridItem(.flexible()),
            ], spacing: 12) {
                ForEach(viewModel.crimeStats) { stat in
                    HistoricalStatCard(stat: stat)
                }
            }
        }
    }

    private var recentEventsSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            Label("Recent Events", systemImage: "list.bullet.circle")
                .font(.subheadline.bold())
                .foregroundColor(.secondary)

            ForEach(viewModel.recentEvents) { event in
                HistoricalEventRow(event: event)
            }
        }
    }

    private var loadingView: some View {
        VStack(spacing: 12) {
            ProgressView()
            Text("Loading historical data...")
                .font(.caption)
                .foregroundColor(.secondary)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 40)
    }

    private var emptyStateView: some View {
        VStack(spacing: 12) {
            Image(systemName: "map.circle")
                .font(.largeTitle)
                .foregroundColor(.secondary)
            Text("No historical data available for this location")
                .font(.caption)
                .foregroundColor(.secondary)
                .multilineTextAlignment(.center)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 40)
    }
}

// MARK: - Stat Card

private struct HistoricalStatCard: View {
    let stat: CrimeStat

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack {
                Image(systemName: stat.iconName)
                    .foregroundColor(stat.color)
                Text("\(stat.count)")
                    .font(.title2.bold())
            }
            Text(stat.category)
                .font(.caption)
                .foregroundColor(.secondary)
                .lineLimit(1)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding()
        .background(Color(uiColor: .systemGray6))
        .cornerRadius(12)
    }
}

// MARK: - Event Row

private struct HistoricalEventRow: View {
    let event: HistoricalEvent

    var body: some View {
        HStack(alignment: .top, spacing: 12) {
            // Event type icon
            Image(systemName: iconName(for: event.eventType))
                .font(.title3)
                .foregroundColor(color(for: event.eventType))
                .frame(width: 32, height: 32)
                .background(color(for: event.eventType).opacity(0.15))
                .cornerRadius(8)

            VStack(alignment: .leading, spacing: 2) {
                Text(event.title)
                    .font(.subheadline.bold())
                    .lineLimit(2)

                if let description = event.description {
                    Text(description)
                        .font(.caption)
                        .foregroundColor(.secondary)
                        .lineLimit(2)
                }

                if let dateDisplay = event.dateDisplay {
                    Text(dateDisplay)
                        .font(.caption2)
                        .foregroundColor(.secondary)
                }
            }
        }
        .padding(.vertical, 4)
    }

    private func iconName(for eventType: String) -> String {
        switch eventType {
        case "dispatch_call": return "phone.fill"
        case "police_incident": return "shield.fill"
        case "fire_call": return "flame.fill"
        case "traffic_crash": return "car.fill"
        case "311_case": return "wrench.fill"
        default: return "mappin.circle.fill"
        }
    }

    private func color(for eventType: String) -> Color {
        switch eventType {
        case "dispatch_call": return .blue
        case "police_incident": return .red
        case "fire_call": return .orange
        case "traffic_crash": return .purple
        case "311_case": return .green
        default: return .gray
        }
    }
}

// MARK: - View Model

@MainActor
class HistoricalContextViewModel: ObservableObject {
    @Published var ambientContext: String?
    @Published var neighborhood: String?
    @Published var crimeStats: [CrimeStat] = []
    @Published var recentEvents: [HistoricalEvent] = []
    @Published var isLoading = false
    @Published var error: Error?

    private let diachronClient = DiachronClient.shared

    var isEmpty: Bool {
        !isLoading && ambientContext == nil && crimeStats.isEmpty && recentEvents.isEmpty
    }

    func loadData(for coordinate: CLLocationCoordinate2D) async {
        isLoading = true
        defer { isLoading = false }

        // Load in parallel
        async let ambientTask: () = loadAmbientContext(coordinate)
        async let eventsTask: () = loadCrimeEvents(coordinate)

        _ = await (ambientTask, eventsTask)
    }

    private func loadAmbientContext(_ coordinate: CLLocationCoordinate2D) async {
        do {
            let response = try await diachronClient.fetchAmbientContext(
                latitude: coordinate.latitude,
                longitude: coordinate.longitude,
                radius: 500
            )
            ambientContext = response.context
            neighborhood = response.location?.neighborhood
        } catch {
            print("Failed to load ambient context: \(error)")
            // Non-critical, continue without ambient context
        }
    }

    private func loadCrimeEvents(_ coordinate: CLLocationCoordinate2D) async {
        do {
            let response = try await diachronClient.fetchCrimeEvents(
                latitude: coordinate.latitude,
                longitude: coordinate.longitude,
                radius: 500,
                days: 30,
                limit: 50
            )

            // Convert DiachronEvent to HistoricalEvent
            recentEvents = response.data.prefix(10).map { event in
                HistoricalEvent(
                    id: event.id,
                    title: event.title,
                    eventType: event.eventType,
                    description: event.description,
                    dateDisplay: event.dateDisplay
                )
            }
            crimeStats = computeStats(from: response.data)
        } catch {
            self.error = error
            print("Failed to load crime events: \(error)")
        }
    }

    private func computeStats(from events: [DiachronEvent]) -> [CrimeStat] {
        // Group by event type
        let grouped = Dictionary(grouping: events) { $0.eventType }

        return grouped.map { (eventType, events) in
            CrimeStat(
                category: displayName(for: eventType),
                count: events.count,
                eventType: eventType
            )
        }
        .sorted { $0.count > $1.count }
    }

    private func displayName(for eventType: String) -> String {
        switch eventType {
        case "dispatch_call": return "Police Dispatch"
        case "police_incident": return "Incidents"
        case "fire_call": return "Fire Calls"
        case "traffic_crash": return "Traffic"
        case "311_case": return "311 Cases"
        default: return eventType.replacingOccurrences(of: "_", with: " ").capitalized
        }
    }
}

// MARK: - Models

/// Simplified event model for the historical context view
struct HistoricalEvent: Identifiable {
    let id: String
    let title: String
    let eventType: String
    let description: String?
    let dateDisplay: String?
}

struct CrimeStat: Identifiable {
    let id = UUID()
    let category: String
    let count: Int
    let eventType: String

    var iconName: String {
        switch eventType {
        case "dispatch_call": return "phone.fill"
        case "police_incident": return "shield.fill"
        case "fire_call": return "flame.fill"
        case "traffic_crash": return "car.fill"
        case "311_case": return "wrench.fill"
        default: return "mappin.circle.fill"
        }
    }

    var color: Color {
        switch eventType {
        case "dispatch_call": return .blue
        case "police_incident": return .red
        case "fire_call": return .orange
        case "traffic_crash": return .purple
        case "311_case": return .green
        default: return .gray
        }
    }
}

#Preview {
    HistoricalContextView(
        coordinate: CLLocationCoordinate2D(latitude: 37.7749, longitude: -122.4194),
        onDismiss: {}
    )
}
