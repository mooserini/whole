import Foundation
import FoundationModels

@Generable(description: "A short workstream standup from observed events only.")
struct Standup: Codable {
    @Guide(description: "One sentence. What the stretch of work was.")
    var headline: String

    @Guide(description: "Three to seven facts that happened. No guesses.")
    var happened: [String]

    @Guide(description: "Open threads still unfinished. Empty if none.")
    var open: [String]

    @Guide(description: "Apps or bundle ids actually seen.")
    var apps: [String]
}

struct StandupDocument: Codable {
    var clerk: String
    var generated_at: String
    var event_count: Int
    var truncated: Bool
    var first_ts: String?
    var last_ts: String?
    var standup: Standup
}
