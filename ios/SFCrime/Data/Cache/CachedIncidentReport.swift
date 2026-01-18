import Foundation
import SwiftData

/// SwiftData model for caching incident reports locally.
@Model
final class CachedIncidentReport {
    @Attribute(.unique) var incidentId: String
    var reportId: Int
    var incidentNumber: String?

    var incidentCategory: String?
    var incidentSubcategory: String?
    var incidentDescription: String?
    var resolution: String?

    var incidentDate: Date?
    var incidentTime: String?
    var reportDatetime: Date?

    var latitude: Double?
    var longitude: Double?
    var locationText: String?
    var policeDistrict: String?
    var analysisNeighborhood: String?

    var cachedAt: Date

    init(from report: IncidentReport) {
        self.incidentId = report.incidentId
        self.reportId = report.id
        self.incidentNumber = report.incidentNumber
        self.incidentCategory = report.incidentCategory
        self.incidentSubcategory = report.incidentSubcategory
        self.incidentDescription = report.incidentDescription
        self.resolution = report.resolution
        self.incidentDate = report.incidentDate
        self.incidentTime = report.incidentTime
        self.reportDatetime = report.reportDatetime
        self.latitude = report.coordinates?.latitude
        self.longitude = report.coordinates?.longitude
        self.locationText = report.locationText
        self.policeDistrict = report.policeDistrict
        self.analysisNeighborhood = report.analysisNeighborhood
        self.cachedAt = Date()
    }

    /// Convert back to IncidentReport for use in views
    func toIncidentReport() -> IncidentReport {
        let coords: IncidentReport.Coordinates?
        if let lat = latitude, let lng = longitude {
            coords = IncidentReport.Coordinates(latitude: lat, longitude: lng)
        } else {
            coords = nil
        }

        return IncidentReport(
            id: reportId,
            incidentId: incidentId,
            incidentNumber: incidentNumber,
            incidentCategory: incidentCategory,
            incidentSubcategory: incidentSubcategory,
            incidentDescription: incidentDescription,
            resolution: resolution,
            incidentDate: incidentDate,
            incidentTime: incidentTime,
            reportDatetime: reportDatetime,
            coordinates: coords,
            locationText: locationText,
            policeDistrict: policeDistrict,
            analysisNeighborhood: analysisNeighborhood
        )
    }
}
