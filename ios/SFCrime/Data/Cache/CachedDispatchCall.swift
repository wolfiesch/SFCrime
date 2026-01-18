import Foundation
import SwiftData
import CoreLocation

/// SwiftData model for caching dispatch calls locally.
/// Enables offline access and reduces API calls.
@Model
final class CachedDispatchCall {
    @Attribute(.unique) var cadNumber: String
    var callId: Int
    var callTypeCode: String?
    var callTypeDescription: String?
    var priorityRaw: String?

    var receivedAt: Date
    var dispatchAt: Date?
    var onSceneAt: Date?
    var closedAt: Date?

    var latitude: Double?
    var longitude: Double?
    var locationText: String?
    var district: String?
    var disposition: String?

    var cachedAt: Date

    init(from call: DispatchCall) {
        self.cadNumber = call.cadNumber
        self.callId = call.id
        self.callTypeCode = call.callTypeCode
        self.callTypeDescription = call.callTypeDescription
        self.priorityRaw = call.priority?.rawValue
        self.receivedAt = call.receivedAt
        self.dispatchAt = call.dispatchAt
        self.onSceneAt = call.onSceneAt
        self.closedAt = call.closedAt
        self.latitude = call.coordinates?.latitude
        self.longitude = call.coordinates?.longitude
        self.locationText = call.locationText
        self.district = call.district
        self.disposition = call.disposition
        self.cachedAt = Date()
    }

    /// Convert back to DispatchCall for use in views
    func toDispatchCall() -> DispatchCall {
        let coords: DispatchCall.Coordinates?
        if let lat = latitude, let lng = longitude {
            coords = DispatchCall.Coordinates(latitude: lat, longitude: lng)
        } else {
            coords = nil
        }

        return DispatchCall(
            id: callId,
            cadNumber: cadNumber,
            callTypeCode: callTypeCode,
            callTypeDescription: callTypeDescription,
            priority: priorityRaw.flatMap { Priority(rawValue: $0) },
            receivedAt: receivedAt,
            dispatchAt: dispatchAt,
            onSceneAt: onSceneAt,
            closedAt: closedAt,
            coordinates: coords,
            locationText: locationText,
            district: district,
            disposition: disposition
        )
    }
}
