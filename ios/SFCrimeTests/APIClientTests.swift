import XCTest
@testable import SFCrime

/// Tests for APIClient
final class APIClientTests: XCTestCase {

    var mockSession: URLSession!

    override func setUp() {
        super.setUp()
        // Create a URLSession with mock protocol
        let config = URLSessionConfiguration.ephemeral
        config.protocolClasses = [MockURLProtocol.self]
        mockSession = URLSession(configuration: config)
    }

    override func tearDown() {
        mockSession = nil
        MockURLProtocol.mockResponses.removeAll()
        super.tearDown()
    }

    // MARK: - fetchCalls Tests

    func testFetchCallsSuccess() async throws {
        // Setup mock response
        let responseJSON = """
        {
            "calls": [
                {
                    "id": 1,
                    "cad_number": "240180001",
                    "call_type_code": "459",
                    "call_type_description": "BURGLARY",
                    "priority": "A",
                    "received_at": "2024-01-18T10:30:00.000000+00:00",
                    "coordinates": {
                        "latitude": 37.7749,
                        "longitude": -122.4194
                    },
                    "location_text": "MARKET ST",
                    "district": "SOUTHERN"
                }
            ],
            "next_cursor": null
        }
        """

        MockURLProtocol.mockResponses["/api/v1/calls"] = (
            data: responseJSON.data(using: .utf8)!,
            statusCode: 200
        )

        let client = APIClient(
            baseURL: URL(string: "https://test.example.com")!,
            session: mockSession
        )

        let response = try await client.fetchCalls()

        XCTAssertEqual(response.calls.count, 1)
        XCTAssertEqual(response.calls[0].cadNumber, "240180001")
        XCTAssertEqual(response.calls[0].priority, .a)
        XCTAssertNil(response.nextCursor)
    }

    func testFetchCallsWithPagination() async throws {
        let responseJSON = """
        {
            "calls": [],
            "next_cursor": "cursor_abc123"
        }
        """

        MockURLProtocol.mockResponses["/api/v1/calls"] = (
            data: responseJSON.data(using: .utf8)!,
            statusCode: 200
        )

        let client = APIClient(
            baseURL: URL(string: "https://test.example.com")!,
            session: mockSession
        )

        let response = try await client.fetchCalls(cursor: "previous_cursor", limit: 100)

        XCTAssertEqual(response.nextCursor, "cursor_abc123")
    }

    // MARK: - fetchCallsInBoundingBox Tests

    func testFetchCallsInBoundingBox() async throws {
        let responseJSON = """
        [
            {
                "id": 1,
                "cad_number": "240180001",
                "priority": "B",
                "received_at": "2024-01-18T10:30:00.000000+00:00",
                "coordinates": {
                    "latitude": 37.7749,
                    "longitude": -122.4194
                }
            }
        ]
        """

        MockURLProtocol.mockResponses["/api/v1/calls/bbox"] = (
            data: responseJSON.data(using: .utf8)!,
            statusCode: 200
        )

        let client = APIClient(
            baseURL: URL(string: "https://test.example.com")!,
            session: mockSession
        )

        let calls = try await client.fetchCallsInBoundingBox(
            minLat: 37.0,
            minLng: -123.0,
            maxLat: 38.0,
            maxLng: -122.0
        )

        XCTAssertEqual(calls.count, 1)
        XCTAssertEqual(calls[0].priority, .b)
    }

    // MARK: - Error Handling Tests

    func testNotFoundError() async throws {
        MockURLProtocol.mockResponses["/api/v1/calls/NONEXISTENT"] = (
            data: Data(),
            statusCode: 404
        )

        let client = APIClient(
            baseURL: URL(string: "https://test.example.com")!,
            session: mockSession
        )

        do {
            _ = try await client.fetchCall(cadNumber: "NONEXISTENT")
            XCTFail("Expected error to be thrown")
        } catch let error as APIError {
            XCTAssertEqual(error, .notFound)
        }
    }

    func testRateLimitedError() async throws {
        MockURLProtocol.mockResponses["/api/v1/calls"] = (
            data: Data(),
            statusCode: 429
        )

        let client = APIClient(
            baseURL: URL(string: "https://test.example.com")!,
            session: mockSession
        )

        do {
            _ = try await client.fetchCalls()
            XCTFail("Expected error to be thrown")
        } catch let error as APIError {
            XCTAssertEqual(error, .rateLimited)
        }
    }

    func testServerError() async throws {
        MockURLProtocol.mockResponses["/api/v1/calls"] = (
            data: Data(),
            statusCode: 500
        )

        let client = APIClient(
            baseURL: URL(string: "https://test.example.com")!,
            session: mockSession
        )

        do {
            _ = try await client.fetchCalls()
            XCTFail("Expected error to be thrown")
        } catch let error as APIError {
            if case .serverError(let code) = error {
                XCTAssertEqual(code, 500)
            } else {
                XCTFail("Expected serverError")
            }
        }
    }

    // MARK: - Health Check Tests

    func testCheckHealth() async throws {
        let responseJSON = """
        {
            "status": "healthy",
            "timestamp": "2024-01-18T10:30:00.000000+00:00",
            "dispatch_calls": {
                "last_sync": "2024-01-18T10:25:00.000000+00:00",
                "record_count": 150,
                "oldest_record": null,
                "newest_record": null,
                "date_range": null
            },
            "incident_reports": {
                "last_sync": "2024-01-18T10:00:00.000000+00:00",
                "record_count": 50000,
                "oldest_record": null,
                "newest_record": null,
                "date_range": ["2024-01-01", "2024-01-18"]
            }
        }
        """

        MockURLProtocol.mockResponses["/health"] = (
            data: responseJSON.data(using: .utf8)!,
            statusCode: 200
        )

        let client = APIClient(
            baseURL: URL(string: "https://test.example.com")!,
            session: mockSession
        )

        let health = try await client.checkHealth()

        XCTAssertEqual(health.status, "healthy")
        XCTAssertEqual(health.dispatchCalls.recordCount, 150)
        XCTAssertEqual(health.incidentReports.recordCount, 50000)
    }

    // MARK: - Categories and Districts Tests

    func testFetchCategories() async throws {
        let responseJSON = """
        ["Larceny Theft", "Assault", "Burglary", "Vandalism"]
        """

        MockURLProtocol.mockResponses["/api/v1/incidents/categories"] = (
            data: responseJSON.data(using: .utf8)!,
            statusCode: 200
        )

        let client = APIClient(
            baseURL: URL(string: "https://test.example.com")!,
            session: mockSession
        )

        let categories = try await client.fetchCategories()

        XCTAssertEqual(categories.count, 4)
        XCTAssertTrue(categories.contains("Larceny Theft"))
        XCTAssertTrue(categories.contains("Assault"))
    }

    func testFetchDistricts() async throws {
        let responseJSON = """
        ["Southern", "Central", "Mission", "Northern"]
        """

        MockURLProtocol.mockResponses["/api/v1/incidents/districts"] = (
            data: responseJSON.data(using: .utf8)!,
            statusCode: 200
        )

        let client = APIClient(
            baseURL: URL(string: "https://test.example.com")!,
            session: mockSession
        )

        let districts = try await client.fetchDistricts()

        XCTAssertEqual(districts.count, 4)
        XCTAssertTrue(districts.contains("Southern"))
        XCTAssertTrue(districts.contains("Mission"))
    }
}

// MARK: - APIError Equatable

extension APIError: Equatable {
    public static func == (lhs: APIError, rhs: APIError) -> Bool {
        switch (lhs, rhs) {
        case (.invalidResponse, .invalidResponse):
            return true
        case (.notFound, .notFound):
            return true
        case (.rateLimited, .rateLimited):
            return true
        case (.serverError(let l), .serverError(let r)):
            return l == r
        case (.httpError(let l), .httpError(let r)):
            return l == r
        default:
            return false
        }
    }
}

// MARK: - Mock URL Protocol

class MockURLProtocol: URLProtocol {
    static var mockResponses: [String: (data: Data, statusCode: Int)] = [:]

    override class func canInit(with request: URLRequest) -> Bool {
        return true
    }

    override class func canonicalRequest(for request: URLRequest) -> URLRequest {
        return request
    }

    override func startLoading() {
        guard let url = request.url else {
            client?.urlProtocol(self, didFailWithError: URLError(.badURL))
            return
        }

        // Find matching mock response by path
        let path = url.path
        let matchingKey = MockURLProtocol.mockResponses.keys.first { path.contains($0) }

        if let key = matchingKey, let mockResponse = MockURLProtocol.mockResponses[key] {
            let response = HTTPURLResponse(
                url: url,
                statusCode: mockResponse.statusCode,
                httpVersion: nil,
                headerFields: ["Content-Type": "application/json"]
            )!

            client?.urlProtocol(self, didReceive: response, cacheStoragePolicy: .notAllowed)
            client?.urlProtocol(self, didLoad: mockResponse.data)
            client?.urlProtocolDidFinishLoading(self)
        } else {
            // Default 404 response
            let response = HTTPURLResponse(
                url: url,
                statusCode: 404,
                httpVersion: nil,
                headerFields: nil
            )!
            client?.urlProtocol(self, didReceive: response, cacheStoragePolicy: .notAllowed)
            client?.urlProtocol(self, didLoad: Data())
            client?.urlProtocolDidFinishLoading(self)
        }
    }

    override func stopLoading() {
        // No-op
    }
}
