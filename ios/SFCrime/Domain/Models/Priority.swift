import SwiftUI

/// Call priority levels from DataSF dispatch data.
/// Priority determines response urgency and visual representation.
enum Priority: String, Codable, CaseIterable, Identifiable {
    case a = "A"
    case b = "B"
    case c = "C"

    var id: String { rawValue }

    /// Human-readable display name
    var displayName: String {
        switch self {
        case .a: return "Priority A (Emergency)"
        case .b: return "Priority B (Urgent)"
        case .c: return "Priority C (Routine)"
        }
    }

    /// Short display name for compact UI
    var shortName: String {
        switch self {
        case .a: return "Emergency"
        case .b: return "Urgent"
        case .c: return "Routine"
        }
    }

    /// Color for map markers and UI elements
    var color: Color {
        switch self {
        case .a: return .red
        case .b: return .orange
        case .c: return .yellow
        }
    }

    /// SF Symbol icon name
    var iconName: String {
        switch self {
        case .a: return "exclamationmark.triangle.fill"
        case .b: return "exclamationmark.circle.fill"
        case .c: return "info.circle.fill"
        }
    }

    /// Sort order (A = highest priority = 0)
    var sortOrder: Int {
        switch self {
        case .a: return 0
        case .b: return 1
        case .c: return 2
        }
    }
}
