import Foundation

public enum FlowError: LocalizedError {
    case message(String)
    public var errorDescription: String? { if case .message(let text) = self { return text }; return nil }
}
public enum FlowProtocol {
    public static let maxSize: Int64 = 9_007_199_254_740_991
    public static let maxManifest = 8 * 1024 * 1024
    public static var now: Int64 { Int64(Date().timeIntervalSince1970 * 1000) }
    public static func validCode(_ value: String) -> Bool { value.range(of: "^[A-Z2-9]{8}$", options: .regularExpression) != nil }
    public static func validID(_ value: String) -> Bool { UUID(uuidString: value) != nil }
    public static func safeName(_ input: String) -> String {
        let bad = CharacterSet.controlCharacters.union(CharacterSet(charactersIn: "/\\:"))
        var name = input.components(separatedBy: bad).joined(separator: "_").trimmingCharacters(in: .whitespacesAndNewlines)
        while name.hasSuffix(".") { name.removeLast() }
        if name.isEmpty || name == "." || name == ".." { name = "file" }
        let ext = (name as NSString).pathExtension
        let suffix = ext.utf8.count <= 40 && !ext.isEmpty ? "." + ext : ""
        let stem = suffix.isEmpty ? name : String(name.dropLast(suffix.count))
        var result = ""
        for char in stem { if (result + String(char) + suffix).utf8.count > 190 { break }; result.append(char) }
        return (result.isEmpty ? "file" : result) + suffix
    }
    public static func base(_ url: URL) throws -> URL {
        guard var parts = URLComponents(url: url, resolvingAgainstBaseURL: false), parts.scheme == "http", let host = parts.host, !host.isEmpty, parts.user == nil, parts.password == nil, (parts.port ?? 80) > 0, (parts.port ?? 80) <= 65535 else { throw FlowError.message("Địa chỉ FlowDrop không hợp lệ.") }
        parts.path = ""; parts.query = nil; parts.fragment = nil
        guard let result = parts.url else { throw FlowError.message("Địa chỉ không hợp lệ.") }; return result
    }
}
public struct FlowFile: Codable, Identifiable, Sendable {
    public var id: String, name: String, size: Int64, type: String
    public init(id: String = UUID().uuidString.lowercased(), name: String, size: Int64, type: String) { self.id = id; self.name = name; self.size = size; self.type = type }
}
public struct Manifest: Codable, Sendable {
    public var code: String, files: [FlowFile], createdAt: Int64, expiresAt: Int64
    public var size: Int64 { files.reduce(0) { $0 + $1.size } }
    public func validate() throws {
        guard FlowProtocol.validCode(code), !files.isEmpty else { throw FlowError.message("Danh sách file không hợp lệ.") }
        var total: Int64 = 0
        for file in files {
            guard FlowProtocol.validID(file.id), !file.name.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty, file.name.utf16.count <= 255, file.name.rangeOfCharacter(from: .controlCharacters) == nil, file.size >= 0, file.size <= FlowProtocol.maxSize - total else { throw FlowError.message("Tên hoặc dung lượng file không hợp lệ.") }
            total += file.size
        }
    }
}
public struct PeerConfig: Codable, Sendable {
    public var name: String, deviceName: String, platform: String, version: String, deviceId: String, offerKey: String
    public var direct: Int = 1, sessions: Int = 1
    public init(deviceName: String, platform: String, deviceId: String) { name = "FlowDrop"; self.deviceName = deviceName; self.platform = platform; version = "1.0.2"; self.deviceId = deviceId; offerKey = UUID().uuidString.lowercased() }
}
public struct Peer: Identifiable, Hashable, Sendable {
    public var id: String, name: String, platform: String, base: URL
    public init(config: PeerConfig, base: URL) { id = config.deviceId; name = config.deviceName; platform = config.platform; self.base = base }
}
public struct OfferRequest: Codable, Sendable { public var code: String, port: Int, deviceId: String, offerKey: String, statusToken: String }
public struct OfferReply: Codable, Sendable { public var id: String, state: String, tracking: Int?; public var sessionId: String? }
public struct StatusRequest: Codable, Sendable { public var id: String, token: String }
public struct FlowSession: Codable, Identifiable, Sendable {
    public var id = UUID().uuidString.lowercased(), direction: String, name: String, code: String, count: Int, size: Int64
    public var bytes: Int64 = 0, filesDone = 0, currentName = "", state = "pending", createdAt = FlowProtocol.now, startedAt: Int64 = 0, updatedAt = FlowProtocol.now, finishedAt: Int64 = 0, error = "", connectionError = ""
    public init(direction: String, name: String, code: String, count: Int, size: Int64) { self.direction = direction; self.name = name; self.code = code; self.count = count; self.size = size }
    enum CodingKeys: String, CodingKey { case id,direction,name,code,count,size,bytes,filesDone,currentName,state,createdAt,startedAt,updatedAt,finishedAt,error,connectionError }
    public init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        id = try c.decode(String.self, forKey: .id); direction = try c.decode(String.self, forKey: .direction); name = try c.decode(String.self, forKey: .name); code = try c.decode(String.self, forKey: .code); count = try c.decode(Int.self, forKey: .count); size = try c.decode(Int64.self, forKey: .size)
        bytes = try c.decodeIfPresent(Int64.self, forKey: .bytes) ?? 0; filesDone = try c.decodeIfPresent(Int.self, forKey: .filesDone) ?? 0; currentName = try c.decodeIfPresent(String.self, forKey: .currentName) ?? ""; state = try c.decodeIfPresent(String.self, forKey: .state) ?? "pending"
        createdAt = try c.decodeIfPresent(Int64.self, forKey: .createdAt) ?? 0; startedAt = try c.decodeIfPresent(Int64.self, forKey: .startedAt) ?? 0; updatedAt = try c.decodeIfPresent(Int64.self, forKey: .updatedAt) ?? 0; finishedAt = try c.decodeIfPresent(Int64.self, forKey: .finishedAt) ?? 0
        error = try c.decodeIfPresent(String.self, forKey: .error) ?? ""; connectionError = try c.decodeIfPresent(String.self, forKey: .connectionError) ?? ""
    }
    public var terminal: Bool { ["completed", "failed", "rejected", "expired", "untracked"].contains(state) }
    public var fraction: Double { size > 0 ? min(1, Double(bytes) / Double(size)) : count > 0 ? Double(filesDone) / Double(count) : 0 }
    public var label: String {
        if !connectionError.isEmpty { return "Mất kết nối · Đang thử lại" }
        switch state {
        case "preparing": return "Đang chuẩn bị file"
        case "pending": return "Chờ chấp nhận"
        case "accepted": return "Đã chấp nhận · Đang bắt đầu"
        case "transferring": return bytes == size && filesDone < count ? "Đang hoàn tất lưu file" : "Đang truyền"
        case "completed": return "Hoàn tất · Đã lưu đủ file"
        case "failed": return "Truyền chưa hoàn tất"
        case "rejected": return "Đã từ chối"
        case "expired": return "Yêu cầu hết hạn"
        default: return "Máy nhận chưa hỗ trợ tiến độ"
        }
    }
}
public struct SavedFile: Codable, Identifiable, Sendable {
    public var id: String
    public var name: String
    public var path: String
    public var size: Int64
    public var date: Int64
    public init(id: String = UUID().uuidString.lowercased(), name: String, path: String, size: Int64, date: Int64 = FlowProtocol.now) {
        self.id = id
        self.name = name
        self.path = path
        self.size = size
        self.date = date
    }
    public var url: URL { URL(fileURLWithPath: path) }
}
public struct FileSource: Sendable {
    public var url: URL, name: String, size: Int64, type: String
    public init(url: URL, name: String, size: Int64, type: String) { self.url = url; self.name = name; self.size = size; self.type = type }
}
public enum DiskFiles {
    public static func size(_ url: URL) throws -> Int64 { let values = try FileManager.default.attributesOfItem(atPath: url.path); guard values[.type] as? FileAttributeType == .typeRegular, let number = values[.size] as? NSNumber else { throw FlowError.message("Chỉ chọn file thông thường.") }; return number.int64Value }
    public static func commit(_ source: URL, name: String, directory: URL) throws -> URL {
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        let clean = FlowProtocol.safeName(name), ext = (clean as NSString).pathExtension, stem = (clean as NSString).deletingPathExtension
        for n in 0..<10_000 {
            let candidate = directory.appendingPathComponent(n == 0 ? clean : stem + " (\(n))" + (ext.isEmpty ? "" : "." + ext))
            // moveItem never overwrites an existing destination.
            do { try FileManager.default.moveItem(at: source, to: candidate); return candidate }
            catch let error as NSError { if error.code == NSFileWriteFileExistsError || FileManager.default.fileExists(atPath: candidate.path) { continue }; throw error }
        }
        throw FlowError.message("Có quá nhiều file trùng tên.")
    }
}
