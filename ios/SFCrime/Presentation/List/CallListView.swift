import SwiftUI

/// List view showing recent dispatch calls.
struct CallListView: View {
    @StateObject private var viewModel = CallListViewModel()
    @State private var selectedCall: DispatchCall?

    var body: some View {
        NavigationStack {
            Group {
                if viewModel.isLoading && viewModel.calls.isEmpty {
                    ProgressView("Loading calls...")
                } else if viewModel.calls.isEmpty {
                    ContentUnavailableView(
                        "No Calls",
                        systemImage: "exclamationmark.triangle",
                        description: Text("No dispatch calls available")
                    )
                } else {
                    List {
                        ForEach(viewModel.groupedCalls) { group in
                            Section(header: Text(group.title)) {
                                ForEach(group.calls) { call in
                                    CallRowView(call: call)
                                        .contentShape(Rectangle())
                                        .onTapGesture {
                                            selectedCall = call
                                        }
                                }
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
            .navigationTitle("Recent Calls")
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    if viewModel.isLoading {
                        ProgressView()
                    }
                }
            }
            .refreshable {
                await viewModel.refresh()
            }
            .sheet(item: $selectedCall) { call in
                CallDetailView(call: call)
            }
            .task {
                await viewModel.loadInitialData()
            }
        }
    }
}

// MARK: - Call Row View

struct CallRowView: View {
    let call: DispatchCall

    var body: some View {
        HStack(spacing: 12) {
            PriorityBadge(priority: call.priority ?? .c)

            VStack(alignment: .leading, spacing: 4) {
                Text(call.callTypeDescription ?? "Unknown Incident")
                    .font(.headline)
                    .lineLimit(1)

                Text(call.locationText ?? "Location unavailable")
                    .font(.subheadline)
                    .foregroundColor(.secondary)
                    .lineLimit(1)

                HStack(spacing: 16) {
                    Label(call.timeAgo, systemImage: "clock")

                    if let district = call.district {
                        Label(district, systemImage: "mappin")
                    }

                    if call.isActive {
                        Label("Active", systemImage: "circle.fill")
                            .foregroundColor(.green)
                    }
                }
                .font(.caption)
                .foregroundColor(.secondary)
            }

            Spacer()

            Image(systemName: "chevron.right")
                .foregroundColor(.secondary)
                .font(.caption)
        }
        .padding(.vertical, 4)
    }
}

// MARK: - View Model

@MainActor
class CallListViewModel: ObservableObject {
    @Published var calls: [DispatchCall] = []
    @Published var isLoading = false
    @Published var hasMore = true
    @Published var error: Error?

    private let apiClient = APIClient.shared
    private var nextCursor: String?

    var groupedCalls: [CallGroup] {
        let grouped = Dictionary(grouping: calls) { call in
            Calendar.current.startOfDay(for: call.receivedAt)
        }

        return grouped
            .sorted { $0.key > $1.key }
            .map { date, calls in
                CallGroup(
                    date: date,
                    calls: calls.sorted { $0.receivedAt > $1.receivedAt }
                )
            }
    }

    func loadInitialData() async {
        await fetchCalls()
    }

    func refresh() async {
        nextCursor = nil
        hasMore = true
        await fetchCalls()
    }

    func loadMore() async {
        guard hasMore, !isLoading else { return }
        await fetchCalls()
    }

    private func fetchCalls() async {
        isLoading = true
        defer { isLoading = false }

        do {
            let response = try await apiClient.fetchCalls(
                cursor: nextCursor,
                limit: 50
            )

            if nextCursor == nil {
                calls = response.calls
            } else {
                calls.append(contentsOf: response.calls)
            }

            nextCursor = response.nextCursor
            hasMore = response.nextCursor != nil
            error = nil
        } catch {
            self.error = error
            print("Error fetching calls: \(error)")
        }
    }
}

// MARK: - Call Group

struct CallGroup: Identifiable {
    let date: Date
    let calls: [DispatchCall]

    var id: Date { date }

    var title: String {
        let calendar = Calendar.current
        if calendar.isDateInToday(date) {
            return "Today"
        } else if calendar.isDateInYesterday(date) {
            return "Yesterday"
        } else {
            let formatter = DateFormatter()
            formatter.dateStyle = .medium
            return formatter.string(from: date)
        }
    }
}

#Preview {
    CallListView()
}
