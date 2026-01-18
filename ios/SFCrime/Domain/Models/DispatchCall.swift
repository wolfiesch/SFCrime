import Foundation
import CoreLocation

/// Represents a live 911 dispatch call from DataSF.
/// These are real-time calls with ~10-15 minute delay.
struct DispatchCall: Identifiable, Codable, Hashable {
    let id: Int
    let cadNumber: String
    let callTypeCode: String?
    let callTypeDescription: String?
    let priority: Priority?

    let receivedAt: Date
    let dispatchAt: Date?
    let onSceneAt: Date?
    let closedAt: Date?

    let coordinates: Coordinates?
    let locationText: String?
    let district: String?
    let disposition: String?

    /// Geographic coordinates for map display
    struct Coordinates: Codable, Hashable {
        let latitude: Double
        let longitude: Double

        var clLocationCoordinate: CLLocationCoordinate2D {
            CLLocationCoordinate2D(latitude: latitude, longitude: longitude)
        }
    }

    enum CodingKeys: String, CodingKey {
        case id
        case cadNumber = "cad_number"
        case callTypeCode = "call_type_code"
        case callTypeDescription = "call_type_description"
        case priority
        case receivedAt = "received_at"
        case dispatchAt = "dispatch_at"
        case onSceneAt = "on_scene_at"
        case closedAt = "closed_at"
        case coordinates
        case locationText = "location_text"
        case district
        case disposition
    }

    /// Time since the call was received
    var timeAgo: String {
        let formatter = RelativeDateTimeFormatter()
        formatter.unitsStyle = .abbreviated
        return formatter.localizedString(for: receivedAt, relativeTo: Date())
    }

    /// Whether the call is still active (not closed)
    var isActive: Bool {
        closedAt == nil
    }
}

// MARK: - API Response

/// Paginated response for dispatch calls
struct DispatchCallsResponse: Codable {
    let calls: [DispatchCall]
    let nextCursor: String?
    let total: Int?

    enum CodingKeys: String, CodingKey {
        case calls
        case nextCursor = "next_cursor"
        case total
    }
}
