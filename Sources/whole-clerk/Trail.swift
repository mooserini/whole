import Foundation

struct TrailEvent: Codable, Sendable {
    var ts: String
    var source: String
    var app: String?
    var title: String?
    var detail: String?
    var session_id: String?
    var path: String?

    func line() -> String {
        var parts: [String] = [ts, source]
        if let app, !app.isEmpty { parts.append(app) }
        if let title, !title.isEmpty { parts.append(title) }
        if let detail, !detail.isEmpty { parts.append(detail) }
        if let session_id, !session_id.isEmpty { parts.append("session=\(session_id)") }
        if let path, !path.isEmpty { parts.append(path) }
        return parts.joined(separator: " | ")
    }
}

enum Trail {
    static let defaultPath = FileManager.default.homeDirectoryForCurrentUser
        .appendingPathComponent(".hermes/whole/trail.jsonl")

    static func load(from url: URL) throws -> [TrailEvent] {
        let data = try Data(contentsOf: url)
        guard !data.isEmpty else { return [] }
        let text = String(decoding: data, as: UTF8.self)
        var events: [TrailEvent] = []
        let decoder = JSONDecoder()
        for (index, raw) in text.split(whereSeparator: \.isNewline).enumerated() {
            let line = raw.trimmingCharacters(in: .whitespaces)
            if line.isEmpty { continue }
            do {
                events.append(try decoder.decode(TrailEvent.self, from: Data(line.utf8)))
            } catch {
                throw ClerkError.badEvent(line: index + 1, underlying: error)
            }
        }
        return events
    }

    /// Keep newest events that fit the AFM window. ~3–4 English chars per token;
    /// leave room for instructions + schema + output.
    static func slice(_ events: [TrailEvent], budgetChars: Int = 6_000) -> [TrailEvent] {
        var kept: [TrailEvent] = []
        var used = 0
        for event in events.reversed() {
            let n = event.line().count + 1
            if used + n > budgetChars { break }
            kept.append(event)
            used += n
        }
        return kept.reversed()
    }

    static func render(_ events: [TrailEvent]) -> String {
        events.map { $0.line() }.joined(separator: "\n")
    }
}
