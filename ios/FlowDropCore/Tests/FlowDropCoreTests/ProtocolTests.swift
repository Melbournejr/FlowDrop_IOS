import XCTest
@testable import FlowDropCore

final class ProtocolTests: XCTestCase {
    func testSavedFileHistoryRemainsCompatible() throws {
        let data = Data(#"{"id":"saved-1","name":"video.mp4","path":"/documents/video.mp4","size":5368709120,"date":123456789}"#.utf8)
        let saved = try JSONDecoder().decode(SavedFile.self, from: data)
        XCTAssertEqual(saved.name, "video.mp4")
        XCTAssertEqual(saved.size, 5 * 1024 * 1024 * 1024)
        XCTAssertEqual(saved.date, 123456789)
        let restored = try JSONDecoder().decode(SavedFile.self, from: JSONEncoder().encode(saved))
        XCTAssertEqual(restored.id, saved.id)
        XCTAssertEqual(restored.path, saved.path)
        let created = SavedFile(name: "empty", path: "/documents/empty", size: 0)
        XCTAssertFalse(created.id.isEmpty)
        XCTAssertGreaterThan(created.date, 0)
        // Incomplete history must not be silently treated as a successfully saved file.
        let incomplete = Data(#"{"id":"saved-1","name":"empty","path":"/documents/empty","date":1}"#.utf8)
        XCTAssertThrowsError(try JSONDecoder().decode(SavedFile.self, from: incomplete))
    }
    func testAndroidPendingStatusMayOmitOptionalFields() throws {
        let data = Data(#"{"id":"a","direction":"receive","name":"Android","code":"ABCDEFGH","count":1,"size":0,"state":"pending","createdAt":1,"updatedAt":1}"#.utf8)
        let value = try JSONDecoder().decode(FlowSession.self, from: data)
        XCTAssertEqual(value.bytes, 0); XCTAssertEqual(value.error, ""); XCTAssertFalse(value.terminal)
    }
    func testLargeMetadataAndExactIntegerLimit() throws {
        var manifest = Manifest(code: "ABCDEFGH", files: [FlowFile(name: "large.bin", size: 5 * 1024 * 1024 * 1024, type: "application/octet-stream")], createdAt: 1, expiresAt: 2)
        try manifest.validate()
        manifest.files[0].size = FlowProtocol.maxSize
        manifest.files.append(FlowFile(name: "overflow", size: 1, type: ""))
        XCTAssertThrowsError(try manifest.validate())
    }
    func testCommitPreservesFilesAndContainsPaths() throws {
        let root = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        defer { try? FileManager.default.removeItem(at: root) }
        try FileManager.default.createDirectory(at: root, withIntermediateDirectories: true)
        let directory = root.appendingPathComponent("saved")
        let a = root.appendingPathComponent("a"), b = root.appendingPathComponent("b")
        try Data("first".utf8).write(to: a); try Data().write(to: b)
        let first = try DiskFiles.commit(a, name: "../report.txt", directory: directory)
        let second = try DiskFiles.commit(b, name: "../report.txt", directory: directory)
        XCTAssertEqual(first.deletingLastPathComponent().standardizedFileURL.path, directory.standardizedFileURL.path)
        XCTAssertNotEqual(first, second); XCTAssertEqual(try Data(contentsOf: first), Data("first".utf8)); XCTAssertEqual(try DiskFiles.size(second), 0)
        XCTAssertLessThanOrEqual(FlowProtocol.safeName(String(repeating: "Ả", count: 255) + ".pdf").utf8.count, 190)
    }
    func testHTTPFragmentationAndAmbiguousLengths() throws {
        var parser = HTTPParser()
        XCTAssertNil(try parser.append(Data("POST /api/offers HTTP/1.1\r\nContent-Length: 2\r\n\r\n{".utf8), address: "192.168.1.2"))
        let request = try XCTUnwrap(parser.append(Data("}".utf8), address: "192.168.1.2"))
        XCTAssertEqual(request.body, Data("{}".utf8))
        for header in ["Content-Length: 2\r\nContent-Length: 2", "Transfer-Encoding: chunked", "Content-Length: 8388609", "Content-Length: -1"] {
            var invalid = HTTPParser()
            XCTAssertThrowsError(try invalid.append(Data("POST /api/offers HTTP/1.1\r\n\(header)\r\n\r\n".utf8), address: "192.168.1.2"))
        }
    }
    func testChangedSourceIsNotPublished() async throws {
        let root = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        defer { try? FileManager.default.removeItem(at: root) }
        let store = try HostStore(root: root.appendingPathComponent("cache"), downloads: root.appendingPathComponent("saved"), config: PeerConfig(deviceName: "Test", platform: "ios", deviceId: UUID().uuidString))
        let source = root.appendingPathComponent("file"); try Data([1]).write(to: source)
        do { _ = try await store.prepare([FileSource(url: source, name: "file", size: 2, type: "")]) { _, _, _ in }; XCTFail("Changed source must fail") } catch {}
        let cache = try FileManager.default.contentsOfDirectory(atPath: root.appendingPathComponent("cache").path)
        XCTAssertTrue(cache.isEmpty)
    }
}
