import Foundation

// MARK: - Client -> Server Messages

/// Subscribe message to set viewport and priority filters
struct SubscribeMessage: Codable {
    let type: String = "subscribe"
    let viewport: Viewport?
    let priorities: [String]?

    struct Viewport: Codable {
        let min_lat: Double
        let max_lat: Double
        let min_lng: Double
        let max_lng: Double

        init(minLat: Double, maxLat: Double, minLng: Double, maxLng: Double) {
            self.min_lat = minLat
            self.max_lat = maxLat
            self.min_lng = minLng
            self.max_lng = maxLng
        }
    }
}

/// Ping message for keep-alive
struct PingMessage: Codable {
    let type: String = "ping"
}

// MARK: - Server -> Client Messages

/// Wrapper to decode incoming messages by type
enum ServerMessage {
    case callUpdate(CallUpdateMessage)
    case pong
    case error(String)
    case unknown(String)
}

/// Call update message with new/updated dispatch calls
struct CallUpdateMessage: Codable {
    let type: String
    let data: [DispatchCall]
    let timestamp: Date
}

/// Pong response from server
struct PongMessage: Codable {
    let type: String
}

/// Error message from server
struct ErrorMessage: Codable {
    let type: String
    let message: String
}

// MARK: - Message Parsing

extension ServerMessage {
    /// Parse a server message from JSON data
    static func parse(from data: Data) -> ServerMessage {
        // First decode just the type
        struct TypeWrapper: Codable {
            let type: String
        }

        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601

        guard let wrapper = try? decoder.decode(TypeWrapper.self, from: data) else {
            return .unknown(String(data: data, encoding: .utf8) ?? "invalid")
        }

        switch wrapper.type {
        case "call_update":
            if let message = try? decoder.decode(CallUpdateMessage.self, from: data) {
                return .callUpdate(message)
            }
            return .unknown("Failed to parse call_update")

        case "pong":
            return .pong

        case "error":
            if let message = try? decoder.decode(ErrorMessage.self, from: data) {
                return .error(message.message)
            }
            return .error("Unknown error")

        default:
            return .unknown(wrapper.type)
        }
    }
}
