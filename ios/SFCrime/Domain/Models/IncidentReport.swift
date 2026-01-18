import Foundation
import CoreLocation

/// Represents a historical police incident report from DataSF.
/// These are filed reports that appear 24-72 hours after the incident.
struct IncidentReport: Identifiable, Codable, Hashable {
    let id: Int
    let incidentId: String
    let incidentNumber: String?

    let incidentCategory: String?
    let incidentSubcategory: String?
    let incidentDescription: String?
    let resolution: String?

    let incidentDate: Date?
    let incidentTime: String?  // Time as string since API returns "HH:mm"
    let reportDatetime: Date?

    let coordinates: Coordinates?
    let locationText: String?
    let policeDistrict: String?
    let analysisNeighborhood: String?

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
        case incidentId = "incident_id"
        case incidentNumber = "incident_number"
        case incidentCategory = "incident_category"
        case incidentSubcategory = "incident_subcategory"
        case incidentDescription = "incident_description"
        case resolution
        case incidentDate = "incident_date"
        case incidentTime = "incident_time"
        case reportDatetime = "report_datetime"
        case coordinates
        case locationText = "location_text"
        case policeDistrict = "police_district"
        case analysisNeighborhood = "analysis_neighborhood"
    }

    /// Formatted date string for display
    var formattedDate: String {
        guard let date = incidentDate else { return "Unknown date" }
        let formatter = DateFormatter()
        formatter.dateStyle = .medium
        return formatter.string(from: date)
    }

    /// Category display with fallback
    var displayCategory: String {
        incidentCategory ?? "Unknown"
    }
}

// MARK: - API Response

/// Paginated response for incident reports
struct IncidentReportsResponse: Codable {
    let incidents: [IncidentReport]
    let nextCursor: String?
    let total: Int?

    enum CodingKeys: String, CodingKey {
        case incidents
        case nextCursor = "next_cursor"
        case total
    }
}
