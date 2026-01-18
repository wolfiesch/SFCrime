import SwiftUI
import MapKit
import Combine

/// SwiftUI wrapper for the crime map with call markers and clustering.
/// Uses iOS 17's improved MapKit features with grid-based clustering.
struct CrimeMapView: View {
    let calls: [DispatchCall]
    @Binding var region: MKCoordinateRegion
    @Binding var selectedCall: DispatchCall?

    @State private var position: MapCameraPosition
    @State private var clusters: [CallCluster] = []

    init(calls: [DispatchCall], region: Binding<MKCoordinateRegion>, selectedCall: Binding<DispatchCall?>) {
        self.calls = calls
        self._region = region
        self._selectedCall = selectedCall
        self._position = State(initialValue: .region(region.wrappedValue))
    }

    /// Calls that have valid coordinates for map display
    private var callsWithCoordinates: [DispatchCall] {
        calls.filter { $0.coordinates != nil }
    }

    var body: some View {
        mapContent
            .mapStyle(.standard(elevation: .realistic, pointsOfInterest: .excludingAll))
            .mapControls {
                MapCompass()
                MapScaleView()
            }
            .onChange(of: region) { _, newRegion in
                withAnimation {
                    position = .region(newRegion)
                }
                updateClusters(for: newRegion)
            }
            .onChange(of: calls) { _, _ in
                updateClusters(for: region)
            }
            .onMapCameraChange { context in
                region = context.region
                updateClusters(for: context.region)
            }
            .onAppear {
                updateClusters(for: region)
            }
    }

    @ViewBuilder
    private var mapContent: some View {
        Map(position: $position, selection: $selectedCall) {
            UserAnnotation()

            // Show clusters or individual markers based on clustering results
            ForEach(clusters) { cluster in
                if cluster.count == 1, let call = cluster.calls.first {
                    // Single marker
                    makeAnnotation(for: call)
                } else {
                    // Cluster marker
                    makeClusterAnnotation(for: cluster)
                }
            }
        }
    }

    private func updateClusters(for region: MKCoordinateRegion) {
        // Simple grid-based clustering
        let calls = callsWithCoordinates
        guard !calls.isEmpty else {
            clusters = []
            return
        }

        // Calculate cell size based on zoom level
        let cellSize = max(region.span.latitudeDelta / 8, 0.002)

        var cellMap: [String: [DispatchCall]] = [:]

        for call in calls {
            guard let coords = call.coordinates else { continue }
            let cellX = Int(coords.latitude / cellSize)
            let cellY = Int(coords.longitude / cellSize)
            let key = "\(cellX),\(cellY)"
            cellMap[key, default: []].append(call)
        }

        // Convert to clusters
        clusters = cellMap.map { (_, calls) in
            CallCluster(calls: calls)
        }.sorted { $0.count > $1.count }
    }

    private func makeAnnotation(for call: DispatchCall) -> some MapContent {
        let coords = call.coordinates!
        let isSelected = selectedCall?.id == call.id
        return Annotation(
            call.callTypeDescription ?? "Incident",
            coordinate: coords.clLocationCoordinate,
            anchor: .bottom
        ) {
            CallMarkerView(call: call, isSelected: isSelected)
        }
        .tag(call)
    }

    private func makeClusterAnnotation(for cluster: CallCluster) -> some MapContent {
        Annotation(
            "\(cluster.count) incidents",
            coordinate: cluster.centerCoordinate,
            anchor: .center
        ) {
            ClusterMarkerView(cluster: cluster)
        }
    }
}

// MARK: - Cluster Model

struct CallCluster: Identifiable {
    let id = UUID()
    let calls: [DispatchCall]

    var count: Int { calls.count }

    var centerCoordinate: CLLocationCoordinate2D {
        guard !calls.isEmpty else {
            return CLLocationCoordinate2D(latitude: 37.7749, longitude: -122.4194)
        }

        let validCalls = calls.compactMap { $0.coordinates }
        guard !validCalls.isEmpty else {
            return CLLocationCoordinate2D(latitude: 37.7749, longitude: -122.4194)
        }

        let sumLat = validCalls.reduce(0) { $0 + $1.latitude }
        let sumLng = validCalls.reduce(0) { $0 + $1.longitude }

        return CLLocationCoordinate2D(
            latitude: sumLat / Double(validCalls.count),
            longitude: sumLng / Double(validCalls.count)
        )
    }

    /// Dominant priority in the cluster
    var dominantPriority: Priority {
        let priorityCounts = Dictionary(grouping: calls.compactMap { $0.priority }) { $0 }
        return priorityCounts.max { $0.value.count < $1.value.count }?.key ?? .c
    }
}

// MARK: - Cluster Marker View

struct ClusterMarkerView: View {
    let cluster: CallCluster

    private var backgroundColor: Color {
        cluster.dominantPriority.color
    }

    var body: some View {
        ZStack {
            Circle()
                .fill(backgroundColor.opacity(0.9))
                .frame(width: clusterSize, height: clusterSize)

            Circle()
                .stroke(backgroundColor, lineWidth: 3)
                .frame(width: clusterSize, height: clusterSize)

            Text("\(cluster.count)")
                .font(.system(size: fontSize, weight: .bold))
                .foregroundColor(.white)
        }
        .shadow(color: backgroundColor.opacity(0.5), radius: 4)
    }

    private var clusterSize: CGFloat {
        switch cluster.count {
        case 1...5: return 40
        case 6...20: return 50
        case 21...50: return 60
        default: return 70
        }
    }

    private var fontSize: CGFloat {
        switch cluster.count {
        case 1...5: return 14
        case 6...20: return 16
        case 21...99: return 16
        default: return 14
        }
    }
}

// MARK: - Call Marker View

struct CallMarkerView: View {
    let call: DispatchCall
    let isSelected: Bool

    private var priority: Priority {
        call.priority ?? .c
    }

    var body: some View {
        ZStack {
            // Marker pin
            Image(systemName: priority.iconName)
                .font(.title2)
                .foregroundColor(priority.color)
                .padding(8)
                .background(isSelected ? priority.color.opacity(0.2) : .white)
                .clipShape(Circle())
                .overlay(
                    Circle()
                        .stroke(priority.color, lineWidth: isSelected ? 3 : 2)
                )
                .shadow(color: priority.color.opacity(0.3), radius: isSelected ? 8 : 4)
                .scaleEffect(isSelected ? 1.2 : 1.0)
                .animation(.spring(response: 0.3), value: isSelected)
        }
    }
}

// MARK: - Map View Model

@MainActor
class MapViewModel: ObservableObject {
    @Published var calls: [DispatchCall] = []
    @Published var region: MKCoordinateRegion
    @Published var isLoading = false
    @Published var lastUpdated: Date?
    @Published var error: Error?
    @Published var filters = CallFilters()
    @Published var isWebSocketConnected = false

    private let apiClient = APIClient.shared
    private let locationManager = LocationManager()
    private let webSocketClient = WebSocketClient()
    private var pollingTask: Task<Void, Never>?
    private var cancellables = Set<AnyCancellable>()

    // San Francisco center
    private static let sfCenter = CLLocationCoordinate2D(latitude: 37.7749, longitude: -122.4194)
    private static let defaultSpan = MKCoordinateSpan(latitudeDelta: 0.1, longitudeDelta: 0.1)

    init() {
        self.region = MKCoordinateRegion(
            center: Self.sfCenter,
            span: Self.defaultSpan
        )
        setupWebSocketSubscriptions()
    }

    deinit {
        pollingTask?.cancel()
    }

    // MARK: - WebSocket Integration

    private func setupWebSocketSubscriptions() {
        // Subscribe to WebSocket call updates
        webSocketClient.callUpdates
            .receive(on: DispatchQueue.main)
            .sink { [weak self] newCalls in
                self?.mergeWebSocketUpdates(newCalls)
            }
            .store(in: &cancellables)

        // Track WebSocket connection state
        webSocketClient.$isConnected
            .receive(on: DispatchQueue.main)
            .sink { [weak self] isConnected in
                self?.isWebSocketConnected = isConnected
            }
            .store(in: &cancellables)
    }

    private func mergeWebSocketUpdates(_ newCalls: [DispatchCall]) {
        // Build a dictionary of existing calls by CAD number
        var callsByCAD = Dictionary(uniqueKeysWithValues: calls.map { ($0.cadNumber, $0) })

        // Merge new/updated calls
        for call in newCalls {
            // Apply filters
            if !filters.priorities.isEmpty {
                guard let priority = call.priority,
                      filters.priorities.contains(priority) else {
                    // Remove from existing if it no longer matches filters
                    callsByCAD.removeValue(forKey: call.cadNumber)
                    continue
                }
            }

            // Check if call is in current viewport
            if let coords = call.coordinates {
                let bbox = region.boundingBox
                if coords.latitude >= bbox.minLat && coords.latitude <= bbox.maxLat &&
                   coords.longitude >= bbox.minLng && coords.longitude <= bbox.maxLng {
                    callsByCAD[call.cadNumber] = call
                }
            }
        }

        // Update calls array
        calls = Array(callsByCAD.values).sorted { $0.receivedAt > $1.receivedAt }
        lastUpdated = Date()

        print("[MapViewModel] Merged \(newCalls.count) WebSocket updates, total calls: \(calls.count)")
    }

    private func updateWebSocketSubscription() {
        // Convert current region to viewport
        let priorities = filters.priorities.isEmpty ? nil : filters.priorities.map { $0.rawValue }
        webSocketClient.subscribe(region: region, priorities: priorities)
    }

    // MARK: - Data Loading

    func loadInitialData() async {
        await fetchCalls()
    }

    func refresh() async {
        await fetchCalls()
    }

    func startPolling() {
        // Connect WebSocket for real-time updates
        webSocketClient.connect()
        updateWebSocketSubscription()

        pollingTask?.cancel()

        // Reduced polling frequency when WebSocket connected (fallback every 5 minutes)
        pollingTask = Task { [weak self] in
            while !Task.isCancelled {
                // Poll every 5 minutes as fallback when WebSocket is connected
                // This helps fill gaps after reconnection
                try? await Task.sleep(for: .seconds(300))
                guard let self else { return }
                await self.fetchCalls()
            }
        }
    }

    func stopPolling() {
        webSocketClient.disconnect()
        pollingTask?.cancel()
        pollingTask = nil
    }

    func onRegionChanged() {
        // Update WebSocket subscription when viewport changes
        updateWebSocketSubscription()
    }

    func fetchCalls() async {
        isLoading = true
        defer { isLoading = false }

        do {
            // Fetch calls within current viewport
            let bbox = region.boundingBox
            let fetchedCalls = try await apiClient.fetchCallsInBoundingBox(
                minLat: bbox.minLat,
                minLng: bbox.minLng,
                maxLat: bbox.maxLat,
                maxLng: bbox.maxLng
            )

            // Apply filters
            calls = fetchedCalls.filter { call in
                if !filters.priorities.isEmpty {
                    guard let priority = call.priority,
                          filters.priorities.contains(priority) else {
                        return false
                    }
                }
                return true
            }

            lastUpdated = Date()
            error = nil
        } catch {
            self.error = error
            print("Error fetching calls: \(error)")
        }
    }

    func centerOnUserLocation() {
        if let location = locationManager.location {
            withAnimation {
                region = MKCoordinateRegion(
                    center: location.coordinate,
                    span: MKCoordinateSpan(latitudeDelta: 0.02, longitudeDelta: 0.02)
                )
            }
        }
    }
}

// MARK: - Call Filters

struct CallFilters {
    var priorities: Set<Priority> = []
    var timeRange: TimeRange = .last24Hours

    enum TimeRange: String, CaseIterable, Identifiable {
        case lastHour = "Last Hour"
        case last6Hours = "Last 6 Hours"
        case last24Hours = "Last 24 Hours"
        case last48Hours = "Last 48 Hours"

        var id: String { rawValue }
    }
}

// MARK: - Extensions

extension MKCoordinateRegion: @retroactive Equatable {
    public static func == (lhs: MKCoordinateRegion, rhs: MKCoordinateRegion) -> Bool {
        lhs.center.latitude == rhs.center.latitude &&
        lhs.center.longitude == rhs.center.longitude &&
        lhs.span.latitudeDelta == rhs.span.latitudeDelta &&
        lhs.span.longitudeDelta == rhs.span.longitudeDelta
    }

    var boundingBox: (minLat: Double, minLng: Double, maxLat: Double, maxLng: Double) {
        let minLat = center.latitude - span.latitudeDelta / 2
        let maxLat = center.latitude + span.latitudeDelta / 2
        let minLng = center.longitude - span.longitudeDelta / 2
        let maxLng = center.longitude + span.longitudeDelta / 2
        return (minLat, minLng, maxLat, maxLng)
    }
}

#Preview {
    CrimeMapView(
        calls: [],
        region: .constant(MKCoordinateRegion(
            center: CLLocationCoordinate2D(latitude: 37.7749, longitude: -122.4194),
            span: MKCoordinateSpan(latitudeDelta: 0.1, longitudeDelta: 0.1)
        )),
        selectedCall: .constant(nil)
    )
}
