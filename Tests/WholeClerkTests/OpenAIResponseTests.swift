import XCTest
@testable import whole_clerk

final class OpenAIResponseTests: XCTestCase {
    func testDecodesStandupFromChatCompletionContent() throws {
        let data = Data(#"{"choices":[{"message":{"content":"{\"headline\":\"Built Whole\",\"happened\":[\"Captured events\"],\"open\":[],\"apps\":[\"Hermes\"]}"}}]}"#.utf8)

        let standup = try OpenAIResponse.decodeStandup(from: data)

        XCTAssertEqual(standup.headline, "Built Whole")
        XCTAssertEqual(standup.happened, ["Captured events"])
        XCTAssertEqual(standup.open, [])
        XCTAssertEqual(standup.apps, ["Hermes"])
    }

    func testRejectsCompletionWithoutContent() {
        let data = Data(#"{"choices":[]}"#.utf8)

        XCTAssertThrowsError(try OpenAIResponse.decodeStandup(from: data))
    }
}