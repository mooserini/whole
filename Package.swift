// swift-tools-version: 6.2
import PackageDescription

let package = Package(
    name: "whole",
    platforms: [
        .macOS(.v26)
    ],
    products: [
        .executable(name: "whole-clerk", targets: ["whole-clerk"])
    ],
    targets: [
        .executableTarget(
            name: "whole-clerk",
            path: "Sources/whole-clerk",
            swiftSettings: [.unsafeFlags(["-parse-as-library"])]
        ),
        .testTarget(
            name: "WholeClerkTests",
            dependencies: ["whole-clerk"],
            path: "Tests/WholeClerkTests"
        )
    ]
)
