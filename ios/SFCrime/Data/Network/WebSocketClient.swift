import Foundation
import Combine
import CoreLocation

/// WebSocket client for real-time dispatch call updates.
///
/// Features:
/// - Automatic reconnection with exponential backoff
/// - Viewport-based subscription filtering
/// - Ping/pong keep-alive
/// - Thread-safe connection state management
@MainActor
final class WebSocketClient: ObservableObject {
    // MARK: - Published State

    @Published private(set) var isConnected = false
    @Published private(set) var connectionError: String?

    // MARK: - Publishers

    /// Publisher for incoming call updates
    let callUpdates = PassthroughSubject<[DispatchCall], Never>()

    // MARK: - Configuration

    private let baseURL: URL
    private var webSocketTask: URLSessionWebSocketTask?
    private var session: URLSession

    // Reconnection state
    private var reconnectAttempt = 0
    private let maxReconnectDelay: TimeInterval = 30
    private var reconnectTask: Task<Void, Never>?

    // Keep-alive
    private var pingTask: Task<Void, Never>?
    private let pingInterval: TimeInterval = 30

    // Current subscription
    private var currentViewport: SubscribeMessage.Viewport?
    private var currentPriorities: [String]?

    // MARK: - Initialization

    init(baseURL: URL = URL(string: "wss://sfcrime-api.fly.dev")!) {
        self.baseURL = baseURL
        self.session = URLSession(configuration: .default)
    }

    // MARK: - Connection Management

    /// Connect to the WebSocket server
    func connect() {
        guard webSocketTask == nil else { return }

        let wsURL = baseURL.appendingPathComponent("ws/calls")
        webSocketTask = session.webSocketTask(with: wsURL)
        webSocketTask?.resume()

        isConnected = true
        connectionError = nil
        reconnectAttempt = 0

        // Start receiving messages
        receiveMessage()

        // Start keep-alive pings
        startPingTask()

        // Re-send subscription if we had one
        if currentViewport != nil || currentPriorities != nil {
            sendSubscription(viewport: currentViewport, priorities: currentPriorities)
        }

        print("[WebSocket] Connected to \(wsURL)")
    }

    /// Disconnect from the WebSocket server
    func disconnect() {
        reconnectTask?.cancel()
        reconnectTask = nil
        pingTask?.cancel()
        pingTask = nil

        webSocketTask?.cancel(with: .normalClosure, reason: nil)
        webSocketTask = nil
        isConnected = false

        print("[WebSocket] Disconnected")
    }

    /// Update subscription with new viewport and/or priorities
    func subscribe(viewport: SubscribeMessage.Viewport? = nil, priorities: [String]? = nil) {
        currentViewport = viewport
        currentPriorities = priorities

        if isConnected {
            sendSubscription(viewport: viewport, priorities: priorities)
        }
    }

    /// Subscribe with a MapKit region
    func subscribe(region: MKCoordinateRegion, priorities: [String]? = nil) {
        let viewport = SubscribeMessage.Viewport(
            minLat: region.center.latitude - region.span.latitudeDelta / 2,
            maxLat: region.center.latitude + region.span.latitudeDelta / 2,
            minLng: region.center.longitude - region.span.longitudeDelta / 2,
            maxLng: region.center.longitude + region.span.longitudeDelta / 2
        )
        subscribe(viewport: viewport, priorities: priorities)
    }

    // MARK: - Private Methods

    private func sendSubscription(viewport: SubscribeMessage.Viewport?, priorities: [String]?) {
        let message = SubscribeMessage(viewport: viewport, priorities: priorities)
        send(message)
    }

    private func send<T: Encodable>(_ message: T) {
        guard let data = try? JSONEncoder().encode(message),
              let string = String(data: data, encoding: .utf8) else {
            return
        }

        webSocketTask?.send(.string(string)) { [weak self] error in
            if let error = error {
                print("[WebSocket] Send error: \(error)")
                Task { @MainActor in
                    self?.handleDisconnect()
                }
            }
        }
    }

    private func receiveMessage() {
        webSocketTask?.receive { [weak self] result in
            Task { @MainActor in
                self?.handleReceiveResult(result)
            }
        }
    }

    private func handleReceiveResult(_ result: Result<URLSessionWebSocketTask.Message, Error>) {
        switch result {
        case .success(let message):
            switch message {
            case .string(let text):
                handleTextMessage(text)
            case .data(let data):
                handleDataMessage(data)
            @unknown default:
                break
            }
            // Continue receiving
            receiveMessage()

        case .failure(let error):
            print("[WebSocket] Receive error: \(error)")
            handleDisconnect()
        }
    }

    private func handleTextMessage(_ text: String) {
        guard let data = text.data(using: .utf8) else { return }
        handleDataMessage(data)
    }

    private func handleDataMessage(_ data: Data) {
        let message = ServerMessage.parse(from: data)

        switch message {
        case .callUpdate(let update):
            print("[WebSocket] Received \(update.data.count) call updates")
            callUpdates.send(update.data)

        case .pong:
            // Keep-alive acknowledged
            break

        case .error(let errorMessage):
            print("[WebSocket] Server error: \(errorMessage)")
            connectionError = errorMessage

        case .unknown(let type):
            print("[WebSocket] Unknown message type: \(type)")
        }
    }

    private func handleDisconnect() {
        webSocketTask = nil
        isConnected = false
        pingTask?.cancel()

        // Schedule reconnection
        scheduleReconnect()
    }

    private func scheduleReconnect() {
        reconnectTask?.cancel()

        // Exponential backoff: 1s, 2s, 4s, 8s, 16s, 30s (max)
        let delay = min(pow(2.0, Double(reconnectAttempt)), maxReconnectDelay)
        reconnectAttempt += 1

        print("[WebSocket] Reconnecting in \(delay)s (attempt \(reconnectAttempt))")

        reconnectTask = Task {
            try? await Task.sleep(nanoseconds: UInt64(delay * 1_000_000_000))

            if !Task.isCancelled {
                connect()
            }
        }
    }

    private func startPingTask() {
        pingTask?.cancel()

        pingTask = Task {
            while !Task.isCancelled && isConnected {
                try? await Task.sleep(nanoseconds: UInt64(pingInterval * 1_000_000_000))

                if !Task.isCancelled && isConnected {
                    send(PingMessage())
                }
            }
        }
    }
}

// MARK: - MapKit Integration

import MapKit

extension MKCoordinateRegion {
    /// Create a viewport for WebSocket subscription
    var webSocketViewport: SubscribeMessage.Viewport {
        SubscribeMessage.Viewport(
            minLat: center.latitude - span.latitudeDelta / 2,
            maxLat: center.latitude + span.latitudeDelta / 2,
            minLng: center.longitude - span.longitudeDelta / 2,
            maxLng: center.longitude + span.longitudeDelta / 2
        )
    }
}
