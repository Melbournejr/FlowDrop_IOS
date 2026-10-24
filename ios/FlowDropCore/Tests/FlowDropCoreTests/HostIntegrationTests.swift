#if canImport(Network)
import XCTest
@testable import FlowDropCore

final class HostIntegrationTests: XCTestCase {
    func testConsentStreamingAndReceiverConfirmedCompletion() async throws {
        let root = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        defer { try? FileManager.default.removeItem(at: root) }
        let source = try HostStore(root: root.appendingPathComponent("cache1"), downloads: root.appendingPathComponent("saved1"), config: PeerConfig(deviceName: "Sender", platform: "ios", deviceId: UUID().uuidString))
        let target = try HostStore(root: root.appendingPathComponent("cache2"), downloads: root.appendingPathComponent("saved2"), config: PeerConfig(deviceName: "Receiver", platform: "ipados", deviceId: UUID().uuidString))
        let first = HTTPHost(store: source), second = HTTPHost(store: target)
        defer { first.stop(); second.stop() }
        let port1 = try await first.start(), port2 = try await second.start()
        await source.configure(port: port1); await target.configure(port: port2)
        let file = root.appendingPathComponent("input.bin"), empty = root.appendingPathComponent("empty")
        let bytes = Data((0..<(1024 * 1024 + 7)).map { UInt8($0 % 251) })
        try bytes.write(to: file); try Data().write(to: empty)
        let manifest = try await source.prepare([FileSource(url: file, name: "received.bin", size: Int64(bytes.count), type: "application/octet-stream"), FileSource(url: empty, name: "empty", size: 0, type: "application/octet-stream")]) { _, _, _ in }
        try await source.send(manifest, to: Peer(config: await target.configuration(), base: URL(string: "http://127.0.0.1:\(port2)")!))
        let before = await target.snapshot()
        XCTAssertEqual(before.pending.count, 1); XCTAssertTrue(before.saved.isEmpty)
        let incoming = try XCTUnwrap(before.pending.first)
        await target.accept(incoming.id)
        let after = await target.snapshot()
        XCTAssertEqual(after.sessions.first?.state, "completed"); XCTAssertEqual(after.saved.count, 2)
        XCTAssertEqual(try Data(contentsOf: root.appendingPathComponent("saved2/received.bin")), bytes)
        XCTAssertEqual(try DiskFiles.size(root.appendingPathComponent("saved2/empty")), 0)
        for _ in 0..<50 {
            await source.refresh(); try await Task.sleep(nanoseconds: 100_000_000)
            if await source.snapshot().sessions.first?.state == "completed" { break }
        }
        let final = await source.snapshot()
        XCTAssertEqual(final.sessions.first?.state, "completed"); XCTAssertEqual(final.sessions.first?.filesDone, 2); XCTAssertEqual(final.sessions.first?.bytes, Int64(bytes.count))
        let forbidden = await target.route(HTTPRequest(method: "POST", path: "/api/offers/status", body: try JSONEncoder().encode(StatusRequest(id: incoming.id, token: "wrong")), address: "127.0.0.1"))
        XCTAssertEqual(forbidden.status, 403)
    }
}
#endif
