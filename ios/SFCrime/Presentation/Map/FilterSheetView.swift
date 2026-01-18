import SwiftUI

/// Filter sheet for map view filtering options.
struct FilterSheetView: View {
    @Binding var filters: CallFilters
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            Form {
                Section("Time Range") {
                    Picker("Show incidents from", selection: $filters.timeRange) {
                        ForEach(CallFilters.TimeRange.allCases) { range in
                            Text(range.rawValue).tag(range)
                        }
                    }
                    .pickerStyle(.menu)
                }

                Section("Priority") {
                    ForEach(Priority.allCases) { priority in
                        Toggle(isOn: Binding(
                            get: { filters.priorities.contains(priority) },
                            set: { isOn in
                                if isOn {
                                    filters.priorities.insert(priority)
                                } else {
                                    filters.priorities.remove(priority)
                                }
                            }
                        )) {
                            HStack {
                                Image(systemName: priority.iconName)
                                    .foregroundColor(priority.color)
                                Text(priority.displayName)
                            }
                        }
                    }
                }

                Section {
                    Button("Show All Priorities") {
                        filters.priorities = Set(Priority.allCases)
                    }

                    Button("Clear Priority Filters") {
                        filters.priorities = []
                    }
                }
            }
            .navigationTitle("Filters")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    Button("Reset") {
                        filters = CallFilters()
                    }
                }

                ToolbarItem(placement: .topBarTrailing) {
                    Button("Done") {
                        dismiss()
                    }
                }
            }
        }
    }
}

#Preview {
    FilterSheetView(filters: .constant(CallFilters()))
}
