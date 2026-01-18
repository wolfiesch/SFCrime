import XCTest
@testable import SFCrime

/// Tests for WebSocket message parsing and types
final class WebSocketTests: XCTestCase {

    // MARK: - Message Type Tests

    func testSubscribeMessageEncoding() throws {
        let message = SubscribeMessage(
            viewport: SubscribeMessage.Viewport(
                minLat: 37.0,
                maxLat: 38.0,
                minLng: -123.0,
                maxLng: -122.0
            ),
            priorities: ["A", "B"]
        )

        let encoder = JSONEncoder()
        let data = try encoder.encode(message)
        let json = String(data: data, encoding: .utf8)!

        XCTAssertTrue(json.contains("\"type\":\"subscribe\""))
        XCTAssertTrue(json.contains("\"min_lat\":37"))
        XCTAssertTrue(json.contains("\"priorities\""))
    }

    func testSubscribeMessageWithNilViewport() throws {
        let message = SubscribeMessage(viewport: nil, priorities: nil)

        let encoder = JSONEncoder()
        let data = try encoder.encode(message)
        let json = String(data: data, encoding: .utf8)!

        XCTAssertTrue(json.contains("\"type\":\"subscribe\""))
    }

    func testCallUpdateMessageDecoding() throws {
        let json = """
        {
            "type": "call_update",
            "data": [
                {
                    "id": 1,
                    "cad_number": "240180001",
                    "priority": "A",
                    "received_at": "2024-01-18T10:30:00Z",
                    "coordinates": {
                        "latitude": 37.7749,
                        "longitude": -122.4194
                    }
                }
            ],
            "timestamp": "2024-01-18T10:35:00Z"
        }
        """

        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601

        let data = json.data(using: .utf8)!
        let message = try decoder.decode(CallUpdateMessage.self, from: data)

        XCTAssertEqual(message.type, "call_update")
        XCTAssertEqual(message.data.count, 1)
        XCTAssertEqual(message.data[0].cadNumber, "240180001")
    }

    func testPingPongMessages() throws {
        // Ping
        let ping = PingMessage()
        let encoder = JSONEncoder()
        let pingData = try encoder.encode(ping)
        let pingJson = String(data: pingData, encoding: .utf8)!
        XCTAssertTrue(pingJson.contains("\"type\":\"ping\""))

        // Pong
        let pongJson = #"{"type": "pong"}"#
        let decoder = JSONDecoder()
        let pong = try decoder.decode(PongMessage.self, from: pongJson.data(using: .utf8)!)
        XCTAssertEqual(pong.type, "pong")
    }

    func testErrorMessageDecoding() throws {
        let json = #"{"type": "error", "message": "Invalid subscription"}"#

        let decoder = JSONDecoder()
        let message = try decoder.decode(ErrorMessage.self, from: json.data(using: .utf8)!)

        XCTAssertEqual(message.type, "error")
        XCTAssertEqual(message.message, "Invalid subscription")
    }

    // MARK: - Viewport Tests

    func testViewportEncoding() throws {
        let viewport = SubscribeMessage.Viewport(
            minLat: 37.7,
            maxLat: 37.8,
            minLng: -122.5,
            maxLng: -122.4
        )

        let encoder = JSONEncoder()
        let data = try encoder.encode(viewport)
        let json = String(data: data, encoding: .utf8)!

        XCTAssertTrue(json.contains("\"min_lat\""))
        XCTAssertTrue(json.contains("\"max_lat\""))
        XCTAssertTrue(json.contains("\"min_lng\""))
        XCTAssertTrue(json.contains("\"max_lng\""))
    }

    func testViewportValues() {
        let viewport = SubscribeMessage.Viewport(
            minLat: 37.0,
            maxLat: 38.0,
            minLng: -123.0,
            maxLng: -122.0
        )

        // Verify values are stored correctly
        XCTAssertEqual(viewport.min_lat, 37.0)
        XCTAssertEqual(viewport.max_lat, 38.0)
        XCTAssertEqual(viewport.min_lng, -123.0)
        XCTAssertEqual(viewport.max_lng, -122.0)
    }

    // MARK: - WebSocket Message Type Detection

    func testMessageTypeDetection() throws {
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601

        // Test type field extraction
        let callUpdateJson = #"{"type": "call_update", "data": [], "timestamp": "2024-01-18T10:00:00"}"#
        let pingJson = #"{"type": "ping"}"#
        let pongJson = #"{"type": "pong"}"#
        let errorJson = #"{"type": "error", "message": "test"}"#

        // We can detect message type by decoding the type field first
        struct TypeContainer: Decodable {
            let type: String
        }

        let callUpdate = try decoder.decode(TypeContainer.self, from: callUpdateJson.data(using: .utf8)!)
        XCTAssertEqual(callUpdate.type, "call_update")

        let ping = try decoder.decode(TypeContainer.self, from: pingJson.data(using: .utf8)!)
        XCTAssertEqual(ping.type, "ping")

        let pong = try decoder.decode(TypeContainer.self, from: pongJson.data(using: .utf8)!)
        XCTAssertEqual(pong.type, "pong")

        let error = try decoder.decode(TypeContainer.self, from: errorJson.data(using: .utf8)!)
        XCTAssertEqual(error.type, "error")
    }
}
