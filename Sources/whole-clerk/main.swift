import Foundation
import FoundationModels

@main
struct WholeClerk {
    static func main() async {
        do {
            try await run()
        } catch let error as ClerkError {
            FileHandle.standardError.write(Data("whole-clerk: \(error.description)\n".utf8))
            exit(error.exitCode)
        } catch {
            FileHandle.standardError.write(Data("whole-clerk: \(error)\n".utf8))
            exit(70)
        }
    }

    static func run() async throws {
        let args = Array(CommandLine.arguments.dropFirst())
        if args.contains("-h") || args.contains("--help") {
            throw ClerkError.usage
        }

        var trailURL = Trail.defaultPath
        var asJSON = false
        var asMarkdown = true
        let provider = try ProviderConfiguration(arguments: args)
        var i = 0
        while i < args.count {
            switch args[i] {
            case "--trail":
                i += 1
                guard i < args.count else { throw ClerkError.usage }
                trailURL = URL(fileURLWithPath: args[i])
            case "--json":
                asJSON = true
                asMarkdown = false
            case "--markdown":
                asMarkdown = true
            case "--provider", "--base-url", "--model":
                i += 1
                guard i < args.count else { throw ClerkError.usage }
            default:
                throw ClerkError.usage
            }
            i += 1
        }

        guard FileManager.default.fileExists(atPath: trailURL.path) else {
            throw ClerkError.missingTrail(trailURL)
        }

        let all = try Trail.load(from: trailURL)
        guard !all.isEmpty else { throw ClerkError.emptyTrail }
        let slice = Trail.slice(all)
        let truncated = slice.count != all.count

        let instructions = """
        You are Whole's clerk. Summarize only the workstream events you are given.
        Do not invent apps, titles, or work that is not in the events.
        Do not moralize. Do not use a thinking monologue.
        Headline: one sentence. Happened: observed facts. Open: unfinished threads only.
        Return a JSON object with exactly these fields: headline (string), happened (string array), open (string array), apps (string array).
        """

        let prompt = """
        Turn these \(slice.count) workstream events into a standup.
        Events are newest-capable, oldest first.

        \(Trail.render(slice))
        """

        let generated: Standup
        switch provider.kind {
        case .apple:
            let model = SystemLanguageModel.default
            switch model.availability {
            case .available:
                break
            case .unavailable(let reason):
                throw ClerkError.modelUnavailable(String(describing: reason))
            }
            let session = LanguageModelSession(instructions: instructions)
            session.prewarm()
            do {
                let response = try await session.respond(
                    to: prompt,
                    generating: Standup.self,
                    includeSchemaInPrompt: true,
                    options: GenerationOptions(temperature: 0.2)
                )
                generated = response.content
            } catch {
                throw ClerkError.generation(error)
            }
        case .openAICompatible:
            generated = try await OpenAICompatibleClerk(configuration: provider).generate(
                instructions: instructions,
                prompt: prompt
            )
        }

        let iso = ISO8601DateFormatter()
        iso.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        let document = StandupDocument(
            clerk: provider.identifier,
            generated_at: iso.string(from: Date()),
            event_count: slice.count,
            truncated: truncated,
            first_ts: slice.first?.ts,
            last_ts: slice.last?.ts,
            standup: generated
        )

        if asJSON {
            let encoder = JSONEncoder()
            encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
            let data = try encoder.encode(document)
            FileHandle.standardOutput.write(data)
            FileHandle.standardOutput.write(Data("\n".utf8))
            return
        }

        if asMarkdown {
            print(markdown(document))
        }
    }

    static func markdown(_ document: StandupDocument) -> String {
        var lines: [String] = []
        lines.append("# \(document.standup.headline)")
        lines.append("")
        if let first = document.first_ts, let last = document.last_ts {
            lines.append("_\(first) → \(last)_ · \(document.event_count) events\(document.truncated ? " (sliced)" : "")")
            lines.append("")
        }
        if !document.standup.happened.isEmpty {
            lines.append("## Happened")
            for item in document.standup.happened {
                lines.append("- \(item)")
            }
            lines.append("")
        }
        if !document.standup.open.isEmpty {
            lines.append("## Open")
            for item in document.standup.open {
                lines.append("- \(item)")
            }
            lines.append("")
        }
        if !document.standup.apps.isEmpty {
            lines.append("## Apps")
            lines.append(document.standup.apps.joined(separator: ", "))
            lines.append("")
        }
        lines.append("_clerk: \(document.clerk)_")
        return lines.joined(separator: "\n")
    }
}
