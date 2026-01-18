import XCTest
@testable import SFCrime

/// Tests for domain models
final class ModelTests: XCTestCase {

    // MARK: - Priority Tests

    func testPriorityRawValues() {
        XCTAssertEqual(Priority.a.rawValue, "A")
        XCTAssertEqual(Priority.b.rawValue, "B")
        XCTAssertEqual(Priority.c.rawValue, "C")
    }

    func testPrioritySortOrder() {
        XCTAssertEqual(Priority.a.sortOrder, 0)
        XCTAssertEqual(Priority.b.sortOrder, 1)
        XCTAssertEqual(Priority.c.sortOrder, 2)

        // Test sorting
        let unsorted: [Priority] = [.c, .a, .b]
        let sorted = unsorted.sorted { $0.sortOrder < $1.sortOrder }
        XCTAssertEqual(sorted, [.a, .b, .c])
    }

    func testPriorityDisplayNames() {
        XCTAssertTrue(Priority.a.displayName.contains("Emergency"))
        XCTAssertTrue(Priority.b.displayName.contains("Urgent"))
        XCTAssertTrue(Priority.c.displayName.contains("Routine"))
    }

    func testPriorityShortNames() {
        XCTAssertEqual(Priority.a.shortName, "Emergency")
        XCTAssertEqual(Priority.b.shortName, "Urgent")
        XCTAssertEqual(Priority.c.shortName, "Routine")
    }

    func testPriorityDecoding() throws {
        let json = #"{"priority": "A"}"#
        struct Container: Decodable { let priority: Priority }

        let data = json.data(using: .utf8)!
        let decoded = try JSONDecoder().decode(Container.self, from: data)

        XCTAssertEqual(decoded.priority, .a)
    }

    // MARK: - DispatchCall Tests

    func testDispatchCallDecoding() throws {
        let json = """
        {
            "id": 123,
            "cad_number": "240180001",
            "call_type_code": "459",
            "call_type_description": "BURGLARY",
            "priority": "A",
            "received_at": "2024-01-18T10:30:00Z",
            "dispatch_at": "2024-01-18T10:32:00Z",
            "on_scene_at": null,
            "closed_at": null,
            "coordinates": {
                "latitude": 37.7749,
                "longitude": -122.4194
            },
            "location_text": "MARKET ST / 5TH ST",
            "district": "SOUTHERN",
            "disposition": null
        }
        """

        let data = json.data(using: .utf8)!
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601

        let call = try decoder.decode(DispatchCall.self, from: data)

        XCTAssertEqual(call.id, 123)
        XCTAssertEqual(call.cadNumber, "240180001")
        XCTAssertEqual(call.callTypeCode, "459")
        XCTAssertEqual(call.callTypeDescription, "BURGLARY")
        XCTAssertEqual(call.priority, .a)
        XCTAssertEqual(call.locationText, "MARKET ST / 5TH ST")
        XCTAssertEqual(call.district, "SOUTHERN")
        XCTAssertNotNil(call.coordinates)
        XCTAssertEqual(call.coordinates?.latitude, 37.7749)
        XCTAssertEqual(call.coordinates?.longitude, -122.4194)
        XCTAssertTrue(call.isActive) // closedAt is nil
    }

    func testDispatchCallIsActive() {
        let activeCall = DispatchCall(
            id: 1,
            cadNumber: "123",
            callTypeCode: nil,
            callTypeDescription: nil,
            priority: .a,
            receivedAt: Date(),
            dispatchAt: nil,
            onSceneAt: nil,
            closedAt: nil,
            coordinates: nil,
            locationText: nil,
            district: nil,
            disposition: nil
        )

        XCTAssertTrue(activeCall.isActive)

        let closedCall = DispatchCall(
            id: 2,
            cadNumber: "124",
            callTypeCode: nil,
            callTypeDescription: nil,
            priority: .a,
            receivedAt: Date(),
            dispatchAt: nil,
            onSceneAt: nil,
            closedAt: Date(),
            coordinates: nil,
            locationText: nil,
            district: nil,
            disposition: nil
        )

        XCTAssertFalse(closedCall.isActive)
    }

    func testDispatchCallHashable() {
        // Use the same date for both calls to ensure equality
        let sharedDate = Date()

        let call1 = DispatchCall(
            id: 1,
            cadNumber: "123",
            callTypeCode: nil,
            callTypeDescription: nil,
            priority: .a,
            receivedAt: sharedDate,
            dispatchAt: nil,
            onSceneAt: nil,
            closedAt: nil,
            coordinates: nil,
            locationText: nil,
            district: nil,
            disposition: nil
        )

        let call2 = DispatchCall(
            id: 1,
            cadNumber: "123",
            callTypeCode: nil,
            callTypeDescription: nil,
            priority: .a,
            receivedAt: sharedDate,
            dispatchAt: nil,
            onSceneAt: nil,
            closedAt: nil,
            coordinates: nil,
            locationText: nil,
            district: nil,
            disposition: nil
        )

        XCTAssertEqual(call1, call2)

        var set = Set<DispatchCall>()
        set.insert(call1)
        set.insert(call2)
        XCTAssertEqual(set.count, 1)
    }

    func testCoordinatesToCLLocationCoordinate() {
        let coords = DispatchCall.Coordinates(latitude: 37.7749, longitude: -122.4194)
        let clCoord = coords.clLocationCoordinate

        XCTAssertEqual(clCoord.latitude, 37.7749, accuracy: 0.0001)
        XCTAssertEqual(clCoord.longitude, -122.4194, accuracy: 0.0001)
    }

    // MARK: - DispatchCallsResponse Tests

    func testDispatchCallsResponseDecoding() throws {
        let json = """
        {
            "calls": [
                {
                    "id": 1,
                    "cad_number": "240180001",
                    "priority": "A",
                    "received_at": "2024-01-18T10:30:00Z"
                }
            ],
            "next_cursor": "abc123",
            "total": 100
        }
        """

        let data = json.data(using: .utf8)!
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601

        let response = try decoder.decode(DispatchCallsResponse.self, from: data)

        XCTAssertEqual(response.calls.count, 1)
        XCTAssertEqual(response.nextCursor, "abc123")
        XCTAssertEqual(response.total, 100)
    }

    func testDispatchCallsResponseNullCursor() throws {
        let json = """
        {
            "calls": [],
            "next_cursor": null,
            "total": null
        }
        """

        let data = json.data(using: .utf8)!
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601

        let response = try decoder.decode(DispatchCallsResponse.self, from: data)

        XCTAssertTrue(response.calls.isEmpty)
        XCTAssertNil(response.nextCursor)
        XCTAssertNil(response.total)
    }
}
