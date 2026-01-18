import Foundation

/// API client for Diachron historical context (HistoryAPI).
/// Provides temporal intelligence about locations including crime patterns.
actor DiachronClient {
    /// Shared singleton instance
    static let shared = DiachronClient()

    /// Base URL for the Diachron API
    private let baseURL: URL

    /// JSON decoder for API responses
    private let decoder: JSONDecoder

    /// URL session for network requests
    private let session: URLSession

    init(
        baseURL: URL = URL(string: "https://historyapi.fly.dev")!,
        session: URLSession = .shared
    ) {
        self.baseURL = baseURL
        self.session = session

        self.decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .custom { decoder in
            let container = try decoder.singleValueContainer()
            let dateString = try container.decode(String.self)

            let formats = [
                "yyyy-MM-dd'T'HH:mm:ss.SSSSSSZZZZZ",
                "yyyy-MM-dd'T'HH:mm:ssZZZZZ",
                "yyyy-MM-dd'T'HH:mm:ss",
                "yyyy-MM-dd",
            ]

            for format in formats {
                let formatter = DateFormatter()
                formatter.dateFormat = format
                formatter.locale = Locale(identifier: "en_US_POSIX")
                formatter.timeZone = TimeZone(secondsFromGMT: 0)
                if let date = formatter.date(from: dateString) {
                    return date
                }
            }

            throw DecodingError.dataCorruptedError(
                in: container,
                debugDescription: "Cannot decode date: \(dateString)"
            )
        }
    }

    // MARK: - Events Nearby

    /// Fetch historical events near a location.
    /// - Parameters:
    ///   - latitude: Center latitude
    ///   - longitude: Center longitude
    ///   - radius: Search radius in meters (default 500)
    ///   - eventTypes: Filter by event types (e.g., "dispatch_call", "police_incident")
    ///   - yearFrom: Filter by start year
    ///   - yearTo: Filter by end year
    ///   - limit: Max results (default 20)
    func fetchEventsNearby(
        latitude: Double,
        longitude: Double,
        radius: Int = 500,
        eventTypes: [String]? = nil,
        yearFrom: Int? = nil,
        yearTo: Int? = nil,
        limit: Int = 20
    ) async throws -> DiachronEventsResponse {
        var components = URLComponents(url: baseURL.appendingPathComponent("/v1/events"), resolvingAgainstBaseURL: true)!

        var queryItems: [URLQueryItem] = [
            URLQueryItem(name: "lat", value: String(latitude)),
            URLQueryItem(name: "lng", value: String(longitude)),
            URLQueryItem(name: "radius", value: String(radius)),
            URLQueryItem(name: "limit", value: String(limit)),
        ]

        if let eventTypes = eventTypes {
            for eventType in eventTypes {
                queryItems.append(URLQueryItem(name: "event_type", value: eventType))
            }
        }

        if let yearFrom = yearFrom {
            queryItems.append(URLQueryItem(name: "year_from", value: String(yearFrom)))
        }

        if let yearTo = yearTo {
            queryItems.append(URLQueryItem(name: "year_to", value: String(yearTo)))
        }

        components.queryItems = queryItems

        let request = URLRequest(url: components.url!)
        let (data, response) = try await session.data(for: request)

        try validateResponse(response)
        return try decoder.decode(DiachronEventsResponse.self, from: data)
    }

    // MARK: - Ambient Context

    /// Get brief, conversational historical context for a location.
    /// Returns synthesized 2-3 sentence snippets about the area.
    /// - Parameters:
    ///   - latitude: Location latitude
    ///   - longitude: Location longitude
    ///   - radius: Search radius in meters (default 500)
    func fetchAmbientContext(
        latitude: Double,
        longitude: Double,
        radius: Int = 500
    ) async throws -> AmbientContextResponse {
        var components = URLComponents(url: baseURL.appendingPathComponent("/v1/context/ambient"), resolvingAgainstBaseURL: true)!

        components.queryItems = [
            URLQueryItem(name: "lat", value: String(latitude)),
            URLQueryItem(name: "lng", value: String(longitude)),
            URLQueryItem(name: "radius", value: String(radius)),
        ]

        let request = URLRequest(url: components.url!)
        let (data, response) = try await session.data(for: request)

        try validateResponse(response)
        return try decoder.decode(AmbientContextResponse.self, from: data)
    }

    // MARK: - Crime Statistics

    /// Fetch crime-related events for pattern analysis.
    /// Filters for dispatch_call, police_incident, fire_call, etc.
    func fetchCrimeEvents(
        latitude: Double,
        longitude: Double,
        radius: Int = 500,
        days: Int = 30,
        limit: Int = 100
    ) async throws -> DiachronEventsResponse {
        let calendar = Calendar.current
        let now = Date()
        let yearTo = calendar.component(.year, from: now)

        // Look back specified days
        let lookbackDate = calendar.date(byAdding: .day, value: -days, to: now) ?? now
        let yearFrom = calendar.component(.year, from: lookbackDate)

        return try await fetchEventsNearby(
            latitude: latitude,
            longitude: longitude,
            radius: radius,
            eventTypes: ["dispatch_call", "police_incident", "fire_call", "traffic_crash", "311_case"],
            yearFrom: yearFrom,
            yearTo: yearTo,
            limit: limit
        )
    }

    // MARK: - Event Detail

    /// Fetch a single event by ID.
    func fetchEvent(id: String) async throws -> DiachronEventDetail {
        let url = baseURL.appendingPathComponent("/v1/events/\(id)")
        let request = URLRequest(url: url)
        let (data, response) = try await session.data(for: request)

        try validateResponse(response)
        let wrapper = try decoder.decode(DiachronEventDetailResponse.self, from: data)
        return wrapper.data
    }

    // MARK: - Helpers

    private func validateResponse(_ response: URLResponse) throws {
        guard let httpResponse = response as? HTTPURLResponse else {
            throw DiachronError.invalidResponse
        }

        switch httpResponse.statusCode {
        case 200...299:
            return
        case 404:
            throw DiachronError.notFound
        case 429:
            throw DiachronError.rateLimited
        case 500...599:
            throw DiachronError.serverError(httpResponse.statusCode)
        default:
            throw DiachronError.httpError(httpResponse.statusCode)
        }
    }
}

// MARK: - Errors

enum DiachronError: LocalizedError {
    case invalidResponse
    case notFound
    case rateLimited
    case serverError(Int)
    case httpError(Int)

    var errorDescription: String? {
        switch self {
        case .invalidResponse:
            return "Invalid response from Diachron"
        case .notFound:
            return "Historical data not found"
        case .rateLimited:
            return "Too many requests. Please try again later."
        case .serverError(let code):
            return "Server error (\(code))"
        case .httpError(let code):
            return "HTTP error (\(code))"
        }
    }
}

// MARK: - Response Models

struct DiachronEventsResponse: Codable {
    let data: [DiachronEvent]
    let meta: DiachronMeta
}

struct DiachronEventDetailResponse: Codable {
    let data: DiachronEventDetail
}

struct DiachronMeta: Codable {
    let total: Int
    let limit: Int
    let offset: Int
    let nextCursor: String?
    let appliedFilters: AppliedFilters?

    enum CodingKeys: String, CodingKey {
        case total, limit, offset
        case nextCursor = "next_cursor"
        case appliedFilters = "applied_filters"
    }
}

struct AppliedFilters: Codable {
    let lat: Double?
    let lng: Double?
    let radius: Int?
    let yearFrom: Int?
    let yearTo: Int?
    let era: String?
    let neighborhood: String?
    let categories: [String]?
    let q: String?

    enum CodingKeys: String, CodingKey {
        case lat, lng, radius, era, neighborhood, categories, q
        case yearFrom = "year_from"
        case yearTo = "year_to"
    }
}

struct DiachronEvent: Codable, Identifiable {
    let id: String
    let title: String
    let yearStart: Int?
    let yearEnd: Int?
    let dateDisplay: String?
    let eventType: String
    let significance: String?
    let categories: [String]
    let description: String?
    let summary: String?
    let era: String?
    let timeCertainty: String?
    let location: DiachronLocation

    enum CodingKeys: String, CodingKey {
        case id, title, categories, description, summary, era, location
        case yearStart = "year_start"
        case yearEnd = "year_end"
        case dateDisplay = "date_display"
        case eventType = "event_type"
        case significance
        case timeCertainty = "time_certainty"
    }
}

struct DiachronEventDetail: Codable, Identifiable {
    let id: String
    let title: String
    let yearStart: Int?
    let yearEnd: Int?
    let dateDisplay: String?
    let eventType: String
    let significance: String?
    let categories: [String]
    let description: String?
    let summary: String?
    let era: String?
    let timeCertainty: String?
    let sources: [[String: String]]?
    let images: [[String: String]]?
    let tags: [String]?
    let verificationStatus: String?
    let createdAt: Date?
    let updatedAt: Date?
    let location: DiachronLocation

    enum CodingKeys: String, CodingKey {
        case id, title, categories, description, summary, era, location, sources, images, tags
        case yearStart = "year_start"
        case yearEnd = "year_end"
        case dateDisplay = "date_display"
        case eventType = "event_type"
        case significance
        case timeCertainty = "time_certainty"
        case verificationStatus = "verification_status"
        case createdAt = "created_at"
        case updatedAt = "updated_at"
    }
}

struct DiachronLocation: Codable {
    let id: String
    let coordinates: DiachronCoordinates
    let title: String
    let address: String?
    let neighborhood: String?
    let factCount: Int?

    enum CodingKeys: String, CodingKey {
        case id, coordinates, title, address, neighborhood
        case factCount = "fact_count"
    }
}

struct DiachronCoordinates: Codable {
    let lat: Double
    let lng: Double
}

struct AmbientContextResponse: Codable {
    let context: String?
    let message: String?
    let factsFound: Int?
    let location: AmbientLocation?
    let radiusMeters: Int?

    enum CodingKeys: String, CodingKey {
        case context, message, location
        case factsFound = "facts_found"
        case radiusMeters = "radius_meters"
    }
}

struct AmbientLocation: Codable {
    let address: String?
    let neighborhood: String?
    let coordinates: DiachronCoordinates?
}
