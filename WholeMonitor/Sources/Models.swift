import Foundation

// Shapes verified live 2026-09-25 against whole-mcp 1.0.0 on 127.0.0.1:39400.
// The API speaks nested snake_case — every struct below carries CodingKeys
// so a server-side rename fails loudly here instead of silently decoding nil.

struct LaunchdBlock: Codable {
    let running: Bool?
    let registered: Bool?
    let state: String?
}

struct ProcessBlock: Codable {
    let alive: Bool?
    let pid: Int?
}

struct TrailBlock: Codable {
    let fresh: Bool?
    let ageSeconds: Double?
    let staleAfterSeconds: Double?

    enum CodingKeys: String, CodingKey {
        case fresh
        case ageSeconds = "age_seconds"
        case staleAfterSeconds = "stale_after_seconds"
    }
}

struct WholeHealth: Codable {
    let overall: String?
    let readOnly: Bool?
    let launchd: LaunchdBlock?
    let process: ProcessBlock?
    let trail: TrailBlock?
    let lastObservedAt: String?
    let status: String?

    enum CodingKeys: String, CodingKey {
        case overall
        case readOnly = "read_only"
        case launchd, process, trail
        case lastObservedAt = "last_observed_at"
        case status
    }
}

struct CollectorBlock: Codable {
    let state: String?
    let processAlive: Bool?
    let launchdRegistered: Bool?
    let trailFresh: Bool?
    let trailAgeSeconds: Double?

    enum CodingKeys: String, CodingKey {
        case state
        case processAlive = "process_alive"
        case launchdRegistered = "launchd_registered"
        case trailFresh = "trail_fresh"
        case trailAgeSeconds = "trail_age_seconds"
    }
}

struct WholeStatus: Codable {
    let events: Int?
    let redactedEvents: Int?
    let residualSensitiveFields: Int?
    let activeSecondsLowerBound: Double?
    let lastObservedAt: String?
    let integrity: String?
    let collector: CollectorBlock?

    enum CodingKeys: String, CodingKey {
        case events
        case redactedEvents = "redacted_events"
        case residualSensitiveFields = "residual_sensitive_fields"
        case activeSecondsLowerBound = "active_seconds_lower_bound"
        case lastObservedAt = "last_observed_at"
        case integrity, collector
    }
}

struct CombinedHealth {
    let state: HealthState
    let health: WholeHealth?
    let status: WholeStatus?
    let lastCheck: Date
    let error: String?
}

enum HealthState: String {
    case healthy = "healthy"
    case watching = "watching"
    case down = "down"
    case unknown = "unknown"

    var colorHex: String {
        switch self {
        case .healthy: return "#34C759"
        case .watching: return "#FF9500"
        case .down: return "#FF3B30"
        case .unknown: return "#8E8E93"
        }
    }

    var icon: String {
        // The eye is always the eye. Color carries the state, so Tom never
        // re-learns the shape: green = fresh, yellow = quiet, red = broken.
        // Only the never-connected state keeps the question mark.
        switch self {
        case .healthy: return "eye.fill"
        case .watching: return "eye.fill"
        case .down: return "eye.fill"
        case .unknown: return "questionmark.circle.fill"
        }
    }

    var description: String {
        switch self {
        case .healthy: return "Collecting"
        case .watching: return "Watching"
        case .down: return "Offline"
        case .unknown: return "Checking..."
        }
    }
}
