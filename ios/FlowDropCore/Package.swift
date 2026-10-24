// swift-tools-version: 5.9
import PackageDescription
let package = Package(name: "FlowDropCore", platforms: [.iOS(.v16), .macOS(.v13)], products: [.library(name: "FlowDropCore", targets: ["FlowDropCore"])], targets: [.target(name: "FlowDropCore"), .testTarget(name: "FlowDropCoreTests", dependencies: ["FlowDropCore"])])
