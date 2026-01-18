import Foundation

/// API client for communicating with the SFCrime backend.
/// Uses async/await and URLSession for network requests.
actor APIClient {
    /// Shared singleton instance
    static let shared = APIClient()

    /// Base URL for the API (configure for your deployment)
    private let baseURL: URL

    /// JSON decoder configured for API responses
    private let decoder: JSONDecoder

    /// URL session for network requests
    private let session: URLSession

    init(
        baseURL: URL = URL(string: "https://sfcrime-api.fly.dev")!,
        session: URLSession = .shared
    ) {
        self.baseURL = baseURL
        self.session = session

        // Configure decoder for API date formats
        self.decoder = JSONDecoder()
        let dateFormatter = ISO8601DateFormatter()
        dateFormatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]

        decoder.dateDecodingStrategy = .custom { decoder in
            let container = try decoder.singleValueContainer()
            let dateString = try container.decode(String.self)

            // Try multiple date formats
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

    // MARK: - Dispatch Calls

    /// Fetch live dispatch calls with optional cursor pagination.
    func fetchCalls(
        cursor: String? = nil,
        limit: Int = 50,
        priorities: [Priority]? = nil
    ) async throws -> DispatchCallsResponse {
        var components = URLComponents(url: baseURL.appendingPathComponent("/api/v1/calls"), resolvingAgainstBaseURL: true)!

        var queryItems: [URLQueryItem] = [
            URLQueryItem(name: "limit", value: String(limit))
        ]

        if let cursor = cursor {
            queryItems.append(URLQueryItem(name: "cursor", value: cursor))
        }

        if let priorities = priorities {
            for priority in priorities {
                queryItems.append(URLQueryItem(name: "priority", value: priority.rawValue))
            }
        }

        components.queryItems = queryItems

        let request = URLRequest(url: components.url!)
        let (data, response) = try await session.data(for: request)

        try validateResponse(response)
        return try decoder.decode(DispatchCallsResponse.self, from: data)
    }

    /// Fetch dispatch calls within a map bounding box.
    func fetchCallsInBoundingBox(
        minLat: Double,
        minLng: Double,
        maxLat: Double,
        maxLng: Double,
        limit: Int = 200
    ) async throws -> [DispatchCall] {
        var components = URLComponents(url: baseURL.appendingPathComponent("/api/v1/calls/bbox"), resolvingAgainstBaseURL: true)!

        components.queryItems = [
            URLQueryItem(name: "min_lat", value: String(minLat)),
            URLQueryItem(name: "min_lng", value: String(minLng)),
            URLQueryItem(name: "max_lat", value: String(maxLat)),
            URLQueryItem(name: "max_lng", value: String(maxLng)),
            URLQueryItem(name: "limit", value: String(limit)),
        ]

        let request = URLRequest(url: components.url!)
        let (data, response) = try await session.data(for: request)

        try validateResponse(response)
        return try decoder.decode([DispatchCall].self, from: data)
    }

    /// Fetch a specific dispatch call by CAD number.
    func fetchCall(cadNumber: String) async throws -> DispatchCall {
        let url = baseURL.appendingPathComponent("/api/v1/calls/\(cadNumber)")
        let request = URLRequest(url: url)
        let (data, response) = try await session.data(for: request)

        try validateResponse(response)
        return try decoder.decode(DispatchCall.self, from: data)
    }

    // MARK: - Incident Reports

    /// Search historical incident reports.
    func searchIncidents(
        cursor: String? = nil,
        limit: Int = 50,
        query: String? = nil,
        since: Date? = nil,
        until: Date? = nil,
        district: String? = nil,
        category: String? = nil
    ) async throws -> IncidentReportsResponse {
        var components = URLComponents(url: baseURL.appendingPathComponent("/api/v1/incidents/search"), resolvingAgainstBaseURL: true)!

        var queryItems: [URLQueryItem] = [
            URLQueryItem(name: "limit", value: String(limit))
        ]

        if let cursor = cursor {
            queryItems.append(URLQueryItem(name: "cursor", value: cursor))
        }

        if let query, !query.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            queryItems.append(URLQueryItem(name: "q", value: query))
        }

        if let since = since {
            let formatter = ISO8601DateFormatter()
            queryItems.append(URLQueryItem(name: "since", value: formatter.string(from: since)))
        }

        if let until = until {
            let formatter = ISO8601DateFormatter()
            queryItems.append(URLQueryItem(name: "until", value: formatter.string(from: until)))
        }

        if let district = district {
            queryItems.append(URLQueryItem(name: "district", value: district))
        }

        if let category = category {
            queryItems.append(URLQueryItem(name: "category", value: category))
        }

        components.queryItems = queryItems

        let request = URLRequest(url: components.url!)
        let (data, response) = try await session.data(for: request)

        try validateResponse(response)
        return try decoder.decode(IncidentReportsResponse.self, from: data)
    }

    /// Fetch list of incident categories.
    func fetchCategories() async throws -> [String] {
        let url = baseURL.appendingPathComponent("/api/v1/incidents/categories")
        let request = URLRequest(url: url)
        let (data, response) = try await session.data(for: request)

        try validateResponse(response)
        return try decoder.decode([String].self, from: data)
    }

    /// Fetch list of police districts.
    func fetchDistricts() async throws -> [String] {
        let url = baseURL.appendingPathComponent("/api/v1/incidents/districts")
        let request = URLRequest(url: url)
        let (data, response) = try await session.data(for: request)

        try validateResponse(response)
        return try decoder.decode([String].self, from: data)
    }

    // MARK: - Health

    /// Check API health status.
    func checkHealth() async throws -> HealthResponse {
        let url = baseURL.appendingPathComponent("/health")
        let request = URLRequest(url: url)
        let (data, response) = try await session.data(for: request)

        try validateResponse(response)
        return try decoder.decode(HealthResponse.self, from: data)
    }

    // MARK: - Helpers

    private func validateResponse(_ response: URLResponse) throws {
        guard let httpResponse = response as? HTTPURLResponse else {
            throw APIError.invalidResponse
        }

        switch httpResponse.statusCode {
        case 200...299:
            return
        case 404:
            throw APIError.notFound
        case 429:
            throw APIError.rateLimited
        case 500...599:
            throw APIError.serverError(httpResponse.statusCode)
        default:
            throw APIError.httpError(httpResponse.statusCode)
        }
    }
}

// MARK: - API Errors

enum APIError: LocalizedError {
    case invalidResponse
    case notFound
    case rateLimited
    case serverError(Int)
    case httpError(Int)

    var errorDescription: String? {
        switch self {
        case .invalidResponse:
            return "Invalid response from server"
        case .notFound:
            return "Resource not found"
        case .rateLimited:
            return "Too many requests. Please try again later."
        case .serverError(let code):
            return "Server error (\(code))"
        case .httpError(let code):
            return "HTTP error (\(code))"
        }
    }
}

// MARK: - Health Response

struct HealthResponse: Codable {
    let status: String
    let timestamp: Date
    let dispatchCalls: DataSourceStatus
    let incidentReports: DataSourceStatus

    enum CodingKeys: String, CodingKey {
        case status
        case timestamp
        case dispatchCalls = "dispatch_calls"
        case incidentReports = "incident_reports"
    }
}

struct DataSourceStatus: Codable {
    let lastSync: Date?
    let recordCount: Int
    let oldestRecord: Date?
    let newestRecord: Date?
    let dateRange: [String]?

    enum CodingKeys: String, CodingKey {
        case lastSync = "last_sync"
        case recordCount = "record_count"
        case oldestRecord = "oldest_record"
        case newestRecord = "newest_record"
        case dateRange = "date_range"
    }
}
