import SwiftUI
import MapKit

/// Container view that manages the map and related UI elements.
struct MapContainerView: View {
    @StateObject private var viewModel = MapViewModel()
    @State private var selectedCall: DispatchCall?
    @State private var showingFilters = false

    var body: some View {
        NavigationStack {
            ZStack(alignment: .bottom) {
                // Map
                CrimeMapView(
                    calls: viewModel.calls,
                    region: $viewModel.region,
                    selectedCall: $selectedCall
                )
                .ignoresSafeArea(edges: .top)

                // Bottom info bar
                VStack(spacing: 0) {
                    // "Data as of" indicator
                    if let lastUpdate = viewModel.lastUpdated {
                        DataAsOfView(date: lastUpdate, isLoading: viewModel.isLoading)
                    }

                    // Selected call preview
                    if let call = selectedCall {
                        CallPreviewCard(call: call) {
                            selectedCall = nil
                        }
                        .transition(.move(edge: .bottom).combined(with: .opacity))
                    }
                }
                .animation(.spring(response: 0.3), value: selectedCall)
            }
            .navigationTitle("SF Crime Map")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    Button {
                        viewModel.centerOnUserLocation()
                    } label: {
                        Image(systemName: "location.fill")
                    }
                }

                ToolbarItem(placement: .topBarTrailing) {
                    Button {
                        showingFilters = true
                    } label: {
                        Image(systemName: "line.3.horizontal.decrease.circle")
                    }
                }
            }
            .sheet(isPresented: $showingFilters) {
                FilterSheetView(filters: $viewModel.filters)
            }
            .sheet(item: $selectedCall) { call in
                CallDetailView(call: call)
            }
            .task {
                await viewModel.loadInitialData()
            }
            .onAppear {
                viewModel.startPolling()
            }
            .onDisappear {
                viewModel.stopPolling()
            }
            .refreshable {
                await viewModel.refresh()
            }
        }
    }
}

// MARK: - Data As Of View

struct DataAsOfView: View {
    let date: Date
    let isLoading: Bool

    var body: some View {
        HStack(spacing: 8) {
            if isLoading {
                ProgressView()
                    .scaleEffect(0.8)
            } else {
                Image(systemName: "clock")
                    .foregroundColor(.secondary)
            }

            Text("Data as of: \(date, style: .relative) ago")
                .font(.caption)
                .foregroundColor(.secondary)
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 8)
        .background(.ultraThinMaterial)
        .clipShape(Capsule())
        .padding(.bottom, 8)
    }
}

// MARK: - Call Preview Card

struct CallPreviewCard: View {
    let call: DispatchCall
    let onDismiss: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                PriorityBadge(priority: call.priority ?? .c)

                VStack(alignment: .leading, spacing: 2) {
                    Text(call.callTypeDescription ?? "Unknown Incident")
                        .font(.headline)
                        .lineLimit(1)

                    Text(call.locationText ?? "Location unavailable")
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                        .lineLimit(1)
                }

                Spacer()

                Button {
                    onDismiss()
                } label: {
                    Image(systemName: "xmark.circle.fill")
                        .foregroundColor(.secondary)
                }
            }

            HStack {
                Label(call.timeAgo, systemImage: "clock")
                    .font(.caption)
                    .foregroundColor(.secondary)

                Spacer()

                if let district = call.district {
                    Label(district, systemImage: "mappin.circle")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
            }
        }
        .padding()
        .background(.regularMaterial)
        .clipShape(RoundedRectangle(cornerRadius: 16))
        .padding(.horizontal)
        .padding(.bottom, 8)
        .shadow(radius: 5)
    }
}

// MARK: - Priority Badge

struct PriorityBadge: View {
    let priority: Priority
    var style: Style = .compact

    enum Style {
        case compact
        case large
    }

    var body: some View {
        HStack(spacing: 4) {
            Image(systemName: priority.iconName)

            if style == .large {
                Text(priority.shortName)
                    .font(.caption.bold())
            }
        }
        .foregroundColor(.white)
        .padding(.horizontal, style == .large ? 12 : 8)
        .padding(.vertical, 6)
        .background(priority.color)
        .clipShape(Capsule())
    }
}

#Preview {
    MapContainerView()
}
