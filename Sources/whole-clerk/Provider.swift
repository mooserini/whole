import Foundation

enum ProviderKind: Equatable {
    case apple
    case openAICompatible
}

struct ProviderConfiguration {
    let kind: ProviderKind
    let identifier: String
    let baseURL: URL
    let model: String?
    let apiKey: String?

    init(arguments: [String], environment: [String: String] = ProcessInfo.processInfo.environment) throws {
        var provider = "openrouter"
        var baseURLValue: String?
        var modelValue: String?
        var index = 0

        while index < arguments.count {
            let argument = arguments[index]
            guard ["--provider", "--base-url", "--model"].contains(argument) else {
                index += 1
                continue
            }
            index += 1
            guard index < arguments.count else { throw ClerkError.usage }
            switch argument {
            case "--provider": provider = arguments[index]
            case "--base-url": baseURLValue = arguments[index]
            case "--model": modelValue = arguments[index]
            default: break
            }
            index += 1
        }

        switch provider.lowercased() {
        case "apple", "apple-foundation-models":
            kind = .apple
            identifier = "apple-foundation-models"
            baseURL = URL(string: "http://127.0.0.1/")!
            model = nil
            apiKey = nil
        case "ollama":
            guard let modelValue, !modelValue.isEmpty else { throw ClerkError.usage }
            kind = .openAICompatible
            identifier = "ollama"
            baseURL = try Self.normalizedURL(baseURLValue ?? "http://127.0.0.1:11434/v1")
            model = modelValue
            apiKey = nil
        case "openrouter":
            guard let key = environment["OPENROUTER_API_KEY"] ?? environment["WHOLE_API_KEY"],
                  !key.isEmpty else {
                throw ClerkError.missingCredential("OPENROUTER_API_KEY")
            }
            kind = .openAICompatible
            identifier = "openrouter"
            baseURL = try Self.normalizedURL(baseURLValue ?? "https://openrouter.ai/api/v1")
            model = modelValue ?? "openrouter/free"
            apiKey = key
        case "openai-compatible":
            guard let baseURLValue, let modelValue, !modelValue.isEmpty else { throw ClerkError.usage }
            kind = .openAICompatible
            identifier = "openai-compatible"
            baseURL = try Self.normalizedURL(baseURLValue)
            model = modelValue
            apiKey = environment["WHOLE_API_KEY"]
        default:
            throw ClerkError.usage
        }
    }

    private static func normalizedURL(_ value: String) throws -> URL {
        let normalized = value.hasSuffix("/") ? value : value + "/"
        guard let url = URL(string: normalized), url.scheme != nil, url.host != nil else {
            throw ClerkError.usage
        }
        return url
    }
}

enum OpenAIResponse {
    private struct Envelope: Decodable {
        struct Choice: Decodable {
            struct Message: Decodable {
                let content: String?
            }
            let message: Message
        }
        let choices: [Choice]
    }

    static func decodeStandup(from data: Data) throws -> Standup {
        let envelope = try JSONDecoder().decode(Envelope.self, from: data)
        guard let content = envelope.choices.first?.message.content,
              !content.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else {
            throw ClerkError.invalidProviderResponse("completion contained no message content")
        }
        do {
            return try JSONDecoder().decode(Standup.self, from: Data(content.utf8))
        } catch {
            // Some free-router models ignore response_format and wrap the JSON
            // in prose. Salvage the outermost {...} span before giving up.
            if let salvaged = Self.extractJSONObject(from: content),
               let standup = try? JSONDecoder().decode(Standup.self, from: Data(salvaged.utf8)) {
                return standup
            }
            throw ClerkError.invalidProviderResponse("message content was not a Whole standup: \(error)")
        }
    }

    /// Returns the substring from the first "{" to the last "}", if both exist
    /// in order. Used to salvage JSON from models that wrap it in prose.
    private static func extractJSONObject(from text: String) -> String? {
        guard let start = text.firstIndex(of: "{"),
              let end = text.lastIndex(of: "}"),
              start <= end else { return nil }
        return String(text[start...end])
    }
}

enum OpenAIRequest {
    static func make(
        configuration: ProviderConfiguration,
        instructions: String,
        prompt: String
    ) throws -> URLRequest {
        guard let model = configuration.model else { throw ClerkError.usage }
        let endpoint = configuration.baseURL.appendingPathComponent("chat/completions")
        var request = URLRequest(url: endpoint)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        if let apiKey = configuration.apiKey, !apiKey.isEmpty {
            request.setValue("Bearer \(apiKey)", forHTTPHeaderField: "Authorization")
        }
        let body: [String: Any] = [
            "model": model,
            "temperature": 0.2,
            "response_format": ["type": "json_object"],
            "messages": [
                ["role": "system", "content": instructions],
                ["role": "user", "content": prompt],
            ],
        ]
        request.httpBody = try JSONSerialization.data(withJSONObject: body)
        return request
    }
}

struct OpenAICompatibleClerk {
    let configuration: ProviderConfiguration

    func generate(instructions: String, prompt: String) async throws -> Standup {
        let request = try OpenAIRequest.make(
            configuration: configuration,
            instructions: instructions,
            prompt: prompt
        )
        let (data, response) = try await URLSession.shared.data(for: request)
        guard let http = response as? HTTPURLResponse, (200..<300).contains(http.statusCode) else {
            let status = (response as? HTTPURLResponse)?.statusCode ?? -1
            throw ClerkError.providerRequest("HTTP \(status)")
        }
        return try OpenAIResponse.decodeStandup(from: data)
    }
}
