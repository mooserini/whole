import XCTest
@testable import whole_clerk

final class OpenAIRequestTests: XCTestCase {
    func testBuildsChatCompletionRequestWithoutLeakingKeyIntoBody() throws {
        let configuration = try ProviderConfiguration(
            arguments: [
                "--provider", "openai-compatible",
                "--base-url", "https://example.test/v1",
                "--model", "model-a",
            ],
            environment: ["WHOLE_API_KEY": "secret"]
        )

        let request = try OpenAIRequest.make(
            configuration: configuration,
            instructions: "Use observed events only.",
            prompt: "event one"
        )

        XCTAssertEqual(request.url?.absoluteString, "https://example.test/v1/chat/completions")
        XCTAssertEqual(request.httpMethod, "POST")
        XCTAssertEqual(request.value(forHTTPHeaderField: "Authorization"), "Bearer secret")
        let body = try XCTUnwrap(request.httpBody)
        let object = try XCTUnwrap(JSONSerialization.jsonObject(with: body) as? [String: Any])
        XCTAssertEqual(object["model"] as? String, "model-a")
        XCTAssertNil(String(data: body, encoding: .utf8)?.range(of: "secret"))
        XCTAssertEqual((object["response_format"] as? [String: String])?["type"], "json_object")
    }

    func testOllamaRequestHasNoAuthorizationHeader() throws {
        let configuration = try ProviderConfiguration(
            arguments: ["--provider", "ollama", "--model", "qwen"],
            environment: [:]
        )

        let request = try OpenAIRequest.make(configuration: configuration, instructions: "i", prompt: "p")

        XCTAssertNil(request.value(forHTTPHeaderField: "Authorization"))
    }
}
