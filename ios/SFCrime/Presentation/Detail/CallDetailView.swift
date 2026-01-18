import SwiftUI
import MapKit

/// Detail view for a dispatch call.
struct CallDetailView: View {
    let call: DispatchCall
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 20) {
                    // Header
                    headerSection

                    // Location map
                    if let coords = call.coordinates {
                        locationMapSection(coordinates: coords)
                    }

                    // Details
                    detailsSection

                    // Timeline
                    timelineSection
                }
                .padding()
            }
            .navigationTitle("Call Details")
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

    private var headerSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                PriorityBadge(priority: call.priority ?? .c, style: .large)
                Spacer()
                if call.isActive {
                    Label("Active", systemImage: "circle.fill")
                        .font(.caption.bold())
                        .foregroundColor(.green)
                        .padding(.horizontal, 12)
                        .padding(.vertical, 6)
                        .background(Color.green.opacity(0.1))
                        .clipShape(Capsule())
                }
            }

            Text(call.callTypeDescription ?? "Unknown Incident")
                .font(.title2.bold())

            if let location = call.locationText {
                Label(location, systemImage: "mappin.and.ellipse")
                    .font(.subheadline)
                    .foregroundColor(.secondary)
            }
        }
    }

    private func locationMapSection(coordinates: DispatchCall.Coordinates) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Location")
                .font(.headline)

            Map(initialPosition: .region(MKCoordinateRegion(
                center: coordinates.clLocationCoordinate,
                span: MKCoordinateSpan(latitudeDelta: 0.01, longitudeDelta: 0.01)
            ))) {
                Marker(call.callTypeDescription ?? "Incident", coordinate: coordinates.clLocationCoordinate)
                    .tint(call.priority?.color ?? .yellow)
            }
            .frame(height: 200)
            .clipShape(RoundedRectangle(cornerRadius: 12))
            .allowsHitTesting(false)
        }
    }

    private var detailsSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Details")
                .font(.headline)

            DetailRow(label: "CAD Number", value: call.cadNumber)

            if let typeCode = call.callTypeCode {
                DetailRow(label: "Type Code", value: typeCode)
            }

            if let district = call.district {
                DetailRow(label: "District", value: district)
            }

            if let disposition = call.disposition {
                DetailRow(label: "Disposition", value: disposition)
            }
        }
        .padding()
        .background(Color(.systemGray6))
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }

    private var timelineSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Timeline")
                .font(.headline)

            TimelineRow(label: "Received", date: call.receivedAt, isCompleted: true)

            if let dispatch = call.dispatchAt {
                TimelineRow(label: "Dispatched", date: dispatch, isCompleted: true)
            }

            if let onScene = call.onSceneAt {
                TimelineRow(label: "On Scene", date: onScene, isCompleted: true)
            }

            if let closed = call.closedAt {
                TimelineRow(label: "Closed", date: closed, isCompleted: true)
            } else {
                TimelineRow(label: "Closed", date: nil, isCompleted: false)
            }
        }
        .padding()
        .background(Color(.systemGray6))
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }
}

// MARK: - Detail Row

struct DetailRow: View {
    let label: String
    let value: String

    var body: some View {
        HStack {
            Text(label)
                .foregroundColor(.secondary)
            Spacer()
            Text(value)
                .fontWeight(.medium)
        }
    }
}

// MARK: - Timeline Row

struct TimelineRow: View {
    let label: String
    let date: Date?
    let isCompleted: Bool

    var body: some View {
        HStack(spacing: 12) {
            Circle()
                .fill(isCompleted ? Color.green : Color.gray.opacity(0.3))
                .frame(width: 12, height: 12)

            Text(label)
                .foregroundColor(isCompleted ? .primary : .secondary)

            Spacer()

            if let date = date {
                Text(date, style: .time)
                    .font(.subheadline)
                    .foregroundColor(.secondary)
            } else {
                Text("Pending")
                    .font(.subheadline)
                    .foregroundColor(.secondary)
            }
        }
    }
}

#Preview {
    CallDetailView(call: DispatchCall(
        id: 1,
        cadNumber: "123456789",
        callTypeCode: "ABC",
        callTypeDescription: "Assault - Battery",
        priority: .a,
        receivedAt: Date().addingTimeInterval(-3600),
        dispatchAt: Date().addingTimeInterval(-3500),
        onSceneAt: Date().addingTimeInterval(-3000),
        closedAt: nil,
        coordinates: DispatchCall.Coordinates(latitude: 37.7749, longitude: -122.4194),
        locationText: "Market St / Powell St",
        district: "Central",
        disposition: nil
    ))
}
