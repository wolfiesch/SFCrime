import Foundation

/// San Francisco Police Districts
enum District: String, CaseIterable, Identifiable {
    case bayview = "Bayview"
    case central = "Central"
    case ingleside = "Ingleside"
    case mission = "Mission"
    case northern = "Northern"
    case park = "Park"
    case richmond = "Richmond"
    case southern = "Southern"
    case taraval = "Taraval"
    case tenderloin = "Tenderloin"

    var id: String { rawValue }

    /// Short code used in some API responses
    var code: String {
        switch self {
        case .bayview: return "D"
        case .central: return "A"
        case .ingleside: return "H"
        case .mission: return "C"
        case .northern: return "E"
        case .park: return "F"
        case .richmond: return "G"
        case .southern: return "B"
        case .taraval: return "I"
        case .tenderloin: return "J"
        }
    }
}
