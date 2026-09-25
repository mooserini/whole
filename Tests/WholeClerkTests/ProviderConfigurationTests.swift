import XCTest
@testable import whole_clerk

final class ProviderConfigurationTests: XCTestCase {
    func testOpenRouterIsTheDefaultProvider() throws {
        let configuration = try ProviderConfiguration(
            arguments: [],
            environment: ["OPENROUTER_API_KEY": "router-key"]
        )

        XCTAssertEqual(configuration.kind, .openAICompatible)
        XCTAssertEqual(configuration.identifier, "openrouter")
        XCTAssertEqual(configuration.model, "openrouter/free")
    }

    func testAppleRemainsAvailableAsAnExplicitOptIn() throws {
        let configuration = try ProviderConfiguration(
            arguments: ["--provider", "apple"],
            environment: [:]
        )

        XCTAssertEqual(configuration.kind, .apple)
        XCTAssertEqual(configuration.identifier, "apple-foundation-models")
    }

    func testOllamaUsesItsLocalOpenAICompatibleEndpoint() throws {
        let configuration = try ProviderConfiguration(
            arguments: ["--provider", "ollama", "--model", "qwen3.5:9b"],
            environment: [:]
        )

        XCTAssertEqual(configuration.kind, .openAICompatible)
        XCTAssertEqual(configuration.identifier, "ollama")
        XCTAssertEqual(configuration.baseURL.absoluteString, "http://127.0.0.1:11434/v1/")
        XCTAssertEqual(configuration.model, "qwen3.5:9b")
        XCTAssertNil(configuration.apiKey)
    }

    func testOpenAICompatibleProviderRequiresBaseURLAndModel() {
        XCTAssertThrowsError(
            try ProviderConfiguration(arguments: ["--provider", "openai-compatible"], environment: [:])
        )
    }

    func testOpenAICompatibleProviderReadsKeyFromEnvironment() throws {
        let configuration = try ProviderConfiguration(
            arguments: [
                "--provider", "openai-compatible",
                "--base-url", "https://example.test/v1",
                "--model", "model-a",
            ],
            environment: ["WHOLE_API_KEY": "secret"]
        )

        XCTAssertEqual(configuration.identifier, "openai-compatible")
        XCTAssertEqual(configuration.baseURL.absoluteString, "https://example.test/v1/")
        XCTAssertEqual(configuration.model, "model-a")
        XCTAssertEqual(configuration.apiKey, "secret")
    }

    func testOpenRouterDefaultsToTheFreeRouter() throws {
        let configuration = try ProviderConfiguration(
            arguments: ["--provider", "openrouter"],
            environment: ["OPENROUTER_API_KEY": "router-key"]
        )

        XCTAssertEqual(configuration.kind, .openAICompatible)
        XCTAssertEqual(configuration.identifier, "openrouter")
        XCTAssertEqual(configuration.baseURL.absoluteString, "https://openrouter.ai/api/v1/")
        XCTAssertEqual(configuration.model, "openrouter/free")
        XCTAssertEqual(configuration.apiKey, "router-key")
    }

    func testOpenRouterRequiresAnAPIKey() {
        XCTAssertThrowsError(
            try ProviderConfiguration(arguments: ["--provider", "openrouter"], environment: [:])
        )
    }
}