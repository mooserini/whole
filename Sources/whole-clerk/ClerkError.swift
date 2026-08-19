import Foundation

enum ClerkError: Error, CustomStringConvertible {
    case usage
    case missingTrail(URL)
    case emptyTrail
    case badEvent(line: Int, underlying: Error)
    case modelUnavailable(String)
    case generation(Error)

    var description: String {
        switch self {
        case .usage:
            return "usage: whole-clerk [--trail PATH] [--json] [--markdown]"
        case .missingTrail(let url):
            return "no trail at \(url.path)"
        case .emptyTrail:
            return "trail is empty"
        case .badEvent(let line, let underlying):
            return "bad event on line \(line): \(underlying)"
        case .modelUnavailable(let reason):
            return "Apple on-device model unavailable: \(reason)"
        case .generation(let error):
            return "generation failed: \(error)"
        }
    }

    var exitCode: Int32 {
        switch self {
        case .usage: return 64
        case .missingTrail, .emptyTrail, .badEvent: return 66
        case .modelUnavailable: return 69
        case .generation: return 70
        }
    }
}
