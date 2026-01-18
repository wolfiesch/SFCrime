import SwiftUI
import MapKit

/// Archive view for searching historical incident reports.
struct ArchiveView: View {
    @StateObject private var viewModel = ArchiveViewModel()
    @State private var showingFilters = false
    @State private var selectedIncident: IncidentReport?

    var body: some View {
        NavigationStack {
            Group {
                if viewModel.isLoading && viewModel.incidents.isEmpty {
                    ProgressView("Searching...")
                } else if viewModel.incidents.isEmpty && viewModel.hasSearched {
                    ContentUnavailableView(
                        "No Results",
                        systemImage: "magnifyingglass",
                        description: Text("Try adjusting your filters")
                    )
                } else if viewModel.incidents.isEmpty {
                    ContentUnavailableView(
                        "Search Archive",
                        systemImage: "clock.arrow.circlepath",
                        description: Text("Search historical incident reports from 2018 to present")
                    )
                } else {
                    List {
                        ForEach(viewModel.incidents) { incident in
                            IncidentRowView(incident: incident)
                                .contentShape(Rectangle())
                                .onTapGesture {
                                    selectedIncident = incident
                                }
                        }

                        // Load more button
                        if viewModel.hasMore {
                            HStack {
                                Spacer()
                                Button("Load More") {
                                    Task {
                                        await viewModel.loadMore()
                                    }
                                }
                                .disabled(viewModel.isLoading)
                                Spacer()
                            }
                            .listRowBackground(Color.clear)
                        }
                    }
                    .listStyle(.insetGrouped)
                }
            }
            .navigationTitle("Archive")
            .searchable(text: $viewModel.searchText, prompt: "Search incidents...")
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button {
                        showingFilters = true
                    } label: {
                        Image(systemName: "line.3.horizontal.decrease.circle")
                            .symbolVariant(viewModel.hasActiveFilters ? .fill : .none)
                    }
                }

                ToolbarItem(placement: .topBarTrailing) {
                    if viewModel.isLoading {
                        ProgressView()
                    }
                }
            }
            .sheet(isPresented: $showingFilters) {
                ArchiveFilterSheet(filters: $viewModel.filters) {
                    Task {
                        await viewModel.search()
                    }
                }
            }
            .sheet(item: $selectedIncident) { incident in
                IncidentDetailView(incident: incident)
            }
            .onSubmit(of: .search) {
                Task {
                    await viewModel.search()
                }
            }
        }
    }
}

// MARK: - Incident Row View

struct IncidentRowView: View {
    let incident: IncidentReport

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Text(incident.displayCategory)
                    .font(.headline)

                Spacer()

                Text(incident.formattedDate)
                    .font(.caption)
                    .foregroundColor(.secondary)
            }

            if let description = incident.incidentDescription {
                Text(description)
                    .font(.subheadline)
                    .foregroundColor(.secondary)
                    .lineLimit(2)
            }

            HStack(spacing: 16) {
                if let location = incident.locationText {
                    Label(location, systemImage: "mappin")
                        .lineLimit(1)
                }

                if let district = incident.policeDistrict {
                    Label(district, systemImage: "building.2")
                }
            }
            .font(.caption)
            .foregroundColor(.secondary)
        }
        .padding(.vertical, 4)
    }
}

// MARK: - View Model

@MainActor
class ArchiveViewModel: ObservableObject {
    @Published var incidents: [IncidentReport] = []
    @Published var isLoading = false
    @Published var hasMore = true
    @Published var hasSearched = false
    @Published var searchText = ""
    @Published var filters = ArchiveFilters()

    private let apiClient = APIClient.shared
    private var nextCursor: String?

    var hasActiveFilters: Bool {
        filters.selectedDistrict != nil ||
        filters.selectedCategory != nil ||
        filters.startDate != nil ||
        filters.endDate != nil
    }

    func search() async {
        nextCursor = nil
        hasMore = true
        hasSearched = true
        incidents = []
        await fetchIncidents()
    }

    func loadMore() async {
        guard hasMore, !isLoading else { return }
        await fetchIncidents()
    }

    private func fetchIncidents() async {
        isLoading = true
        defer { isLoading = false }

        do {
            let response = try await apiClient.searchIncidents(
                cursor: nextCursor,
                limit: 50,
                query: searchText,
                since: filters.startDate,
                until: filters.endDate,
                district: filters.selectedDistrict,
                category: filters.selectedCategory
            )

            incidents.append(contentsOf: response.incidents)
            nextCursor = response.nextCursor
            hasMore = response.nextCursor != nil
        } catch {
            print("Error searching incidents: \(error)")
        }
    }
}

// MARK: - Archive Filters

struct ArchiveFilters {
    var startDate: Date?
    var endDate: Date?
    var selectedDistrict: String?
    var selectedCategory: String?
}

// MARK: - Archive Filter Sheet

struct ArchiveFilterSheet: View {
    @Binding var filters: ArchiveFilters
    let onApply: () -> Void
    @Environment(\.dismiss) private var dismiss

    @State private var categories: [String] = []
    @State private var districts: [String] = []

    var body: some View {
        NavigationStack {
            Form {
                Section("Date Range") {
                    DatePicker(
                        "Start Date",
                        selection: Binding(
                            get: { filters.startDate ?? Date().addingTimeInterval(-30 * 24 * 3600) },
                            set: { filters.startDate = $0 }
                        ),
                        displayedComponents: .date
                    )

                    DatePicker(
                        "End Date",
                        selection: Binding(
                            get: { filters.endDate ?? Date() },
                            set: { filters.endDate = $0 }
                        ),
                        displayedComponents: .date
                    )
                }

                Section("Location") {
                    Picker("District", selection: $filters.selectedDistrict) {
                        Text("All Districts").tag(nil as String?)
                        ForEach(districts, id: \.self) { district in
                            Text(district).tag(district as String?)
                        }
                    }
                }

                Section("Type") {
                    Picker("Category", selection: $filters.selectedCategory) {
                        Text("All Categories").tag(nil as String?)
                        ForEach(categories, id: \.self) { category in
                            Text(category).tag(category as String?)
                        }
                    }
                }
            }
            .navigationTitle("Filters")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    Button("Reset") {
                        filters = ArchiveFilters()
                    }
                }

                ToolbarItem(placement: .topBarTrailing) {
                    Button("Apply") {
                        onApply()
                        dismiss()
                    }
                }
            }
            .task {
                await loadFilterOptions()
            }
        }
    }

    private func loadFilterOptions() async {
        let client = APIClient.shared
        do {
            categories = try await client.fetchCategories()
            districts = try await client.fetchDistricts()
        } catch {
            print("Error loading filter options: \(error)")
        }
    }
}

// MARK: - Incident Detail View

struct IncidentDetailView: View {
    let incident: IncidentReport
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 16) {
                    // Header
                    VStack(alignment: .leading, spacing: 8) {
                        Text(incident.displayCategory)
                            .font(.title2.bold())

                        if let subcategory = incident.incidentSubcategory {
                            Text(subcategory)
                                .font(.subheadline)
                                .foregroundColor(.secondary)
                        }
                    }

                    Divider()

                    // Location map
                    if let coords = incident.coordinates {
                        locationMapSection(coordinates: coords)
                    }

                    // Description
                    if let description = incident.incidentDescription {
                        VStack(alignment: .leading, spacing: 8) {
                            Text("Description")
                                .font(.headline)
                            Text(description)
                        }
                    }

                    // Details
                    VStack(alignment: .leading, spacing: 12) {
                        Text("Details")
                            .font(.headline)

                        DetailRow(label: "Incident ID", value: incident.incidentId)

                        if let number = incident.incidentNumber {
                            DetailRow(label: "Case Number", value: number)
                        }

                        DetailRow(label: "Date", value: incident.formattedDate)

                        if let time = incident.incidentTime {
                            DetailRow(label: "Time", value: time)
                        }

                        if let resolution = incident.resolution {
                            DetailRow(label: "Resolution", value: resolution)
                        }
                    }
                    .padding()
                    .background(Color(.systemGray6))
                    .clipShape(RoundedRectangle(cornerRadius: 12))

                    // Location
                    if incident.locationText != nil || incident.policeDistrict != nil {
                        VStack(alignment: .leading, spacing: 12) {
                            Text("Location")
                                .font(.headline)

                            if let location = incident.locationText {
                                DetailRow(label: "Address", value: location)
                            }

                            if let district = incident.policeDistrict {
                                DetailRow(label: "District", value: district)
                            }

                            if let neighborhood = incident.analysisNeighborhood {
                                DetailRow(label: "Neighborhood", value: neighborhood)
                            }
                        }
                        .padding()
                        .background(Color(.systemGray6))
                        .clipShape(RoundedRectangle(cornerRadius: 12))
                    }
                }
                .padding()
            }
            .navigationTitle("Incident Details")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button("Done") {
                        dismiss()
                    }
                }
            }
        }
    }

    // MARK: - Sections

    private func locationMapSection(coordinates: IncidentReport.Coordinates) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Location")
                .font(.headline)

            Map(initialPosition: .region(MKCoordinateRegion(
                center: coordinates.clLocationCoordinate,
                span: MKCoordinateSpan(latitudeDelta: 0.01, longitudeDelta: 0.01)
            ))) {
                Marker(incident.displayCategory, coordinate: coordinates.clLocationCoordinate)
                    .tint(.blue)
            }
            .frame(height: 200)
            .clipShape(RoundedRectangle(cornerRadius: 12))
            .allowsHitTesting(false)
        }
    }
}

#Preview {
    ArchiveView()
}
