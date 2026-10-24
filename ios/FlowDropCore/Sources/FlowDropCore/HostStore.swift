import Foundation

public struct HTTPRequest: Sendable {
    public let method: String, path: String, headers: [String: String], body: Data, address: String
    public init(method: String, path: String, headers: [String: String] = [:], body: Data = Data(), address: String) { self.method = method; self.path = path; self.headers = headers; self.body = body; self.address = address }
}
public struct HTTPReply: Sendable {
    public enum Body: Sendable { case bytes(Data); case file(URL, Int64, String) }
    public var status: Int, body: Body
    public static func json<T: Encodable>(_ value: T, status: Int = 200) throws -> Self { Self(status: status, body: .bytes(try JSONEncoder().encode(value))) }
    public static func error(_ text: String, status: Int) -> Self { let data = (try? JSONSerialization.data(withJSONObject: ["error": text])) ?? Data(); return Self(status: status, body: .bytes(data)) }
}
public struct StoreSnapshot: Sendable { public var sessions: [FlowSession], pending: [FlowSession], saved: [SavedFile] }
public actor HostStore {
    private struct Cached { var manifest: Manifest, token: String, folder: URL }
    private struct Incoming { var origin: URL, manifest: Manifest, statusToken: String }
    private struct Outgoing { var origin: URL, remoteID: String, token: String }
    private var cached: [String: Cached] = [:], incoming: [String: Incoming] = [:], outgoing: [String: Outgoing] = [:], jobs: [String: FlowSession] = [:]
    private var saved: [SavedFile] = [], polling: Set<String> = []
    private let root: URL, downloads: URL, history: URL, client = HTTPClient()
    private var info: PeerConfig, port = 0
    public init(root: URL, downloads: URL, config: PeerConfig) throws {
        self.root = root; self.downloads = downloads; self.info = config
        history = downloads.appendingPathComponent(".flowdrop-history.json")
        try FileManager.default.createDirectory(at: root, withIntermediateDirectories: true)
        try FileManager.default.createDirectory(at: downloads, withIntermediateDirectories: true)
        // Old outgoing codes are in memory only; do not accumulate orphaned cache across launches.
        for url in (try? FileManager.default.contentsOfDirectory(at: root, includingPropertiesForKeys: nil)) ?? [] where FlowProtocol.validCode(url.lastPathComponent) { try? FileManager.default.removeItem(at: url) }
        if let data = try? Data(contentsOf: history), let old = try? JSONDecoder().decode([SavedFile].self, from: data) { saved = old }
    }
    public func configure(port: Int) { self.port = port }
    public func configuration() -> PeerConfig { info }
    public func rename(_ name: String) { info.deviceName = String(name.trimmingCharacters(in: .whitespacesAndNewlines).prefix(100)) }
    public func snapshot() -> StoreSnapshot {
        expire()
        let sessions = jobs.values.sorted { $0.createdAt > $1.createdAt }
        return StoreSnapshot(sessions: sessions, pending: sessions.filter { $0.direction == "receive" && $0.state == "pending" }, saved: saved)
    }
    private func update(_ id: String, _ action: (inout FlowSession) -> Void) { guard var job = jobs[id] else { return }; action(&job); job.updatedAt = FlowProtocol.now; if job.terminal { job.finishedAt = job.updatedAt }; jobs[id] = job }
    private func expire() {
        for (id, job) in jobs where job.direction == "receive" && job.state == "pending" && FlowProtocol.now - job.createdAt > 120_000 { update(id) { $0.state = "expired" } }
        for (id, job) in jobs where !job.terminal && FlowProtocol.now - job.createdAt > 86_400_000 { update(id) { $0.state = "expired" } }
        let old = jobs.values.filter(\.terminal).sorted { $0.createdAt > $1.createdAt }.dropFirst(50)
        for job in old { jobs.removeValue(forKey: job.id); incoming.removeValue(forKey: job.id); outgoing.removeValue(forKey: job.id) }
        for (code, item) in cached where item.manifest.expiresAt < FlowProtocol.now { try? FileManager.default.removeItem(at: item.folder); cached.removeValue(forKey: code) }
    }
    public func prepare(_ sources: [FileSource], progress: @escaping @Sendable (Int64, Int64, String) -> Void) async throws -> Manifest {
        guard !sources.isEmpty else { throw FlowError.message("Chọn ít nhất một file.") }
        let alphabet = Array("ABCDEFGHJKLMNPQRSTUVWXYZ23456789")
        var code = ""
        repeat { code = String((0..<8).map { _ in alphabet.randomElement()! }) } while cached[code] != nil
        let manifest = Manifest(code: code, files: sources.map { FlowFile(name: $0.name, size: $0.size, type: $0.type) }, createdAt: FlowProtocol.now, expiresAt: FlowProtocol.now + 86_400_000)
        try manifest.validate(); guard try JSONEncoder().encode(manifest).count <= FlowProtocol.maxManifest - 4096 else { throw FlowError.message("Danh sách tên file quá dài.") }
        let folder = root.appendingPathComponent(code, isDirectory: true)
        let work = Task.detached(priority: .utility) {
            do {
                try FileManager.default.createDirectory(at: folder, withIntermediateDirectories: true)
                var total: Int64 = 0, last = Date.distantPast
                for (index, source) in sources.enumerated() {
                    try Task.checkCancellation()
                    guard try DiskFiles.size(source.url) == source.size else { throw FlowError.message("File đã thay đổi. Chọn lại \(source.name).") }
                    let target = folder.appendingPathComponent(manifest.files[index].id)
                    guard FileManager.default.createFile(atPath: target.path, contents: nil) else { throw FlowError.message("Không tạo được bản tạm.") }
                    let input = try FileHandle(forReadingFrom: source.url), output = try FileHandle(forWritingTo: target)
                    do {
                        defer { try? input.close(); try? output.close() }
                        var count: Int64 = 0
                        while let data = try input.read(upToCount: 65_536), !data.isEmpty {
                            try Task.checkCancellation(); count += Int64(data.count)
                            guard count <= source.size else { throw FlowError.message("Dung lượng file đã thay đổi.") }
                            try output.write(contentsOf: data)
                            if Date().timeIntervalSince(last) > 0.2 { last = Date(); progress(total + count, manifest.size, source.name) }
                        }
                        guard count == source.size else { throw FlowError.message("Chưa đọc đủ file \(source.name).") }
                        total += count; progress(total, manifest.size, source.name)
                    }
                }
            } catch { try? FileManager.default.removeItem(at: folder); throw error }
        }
        try await withTaskCancellationHandler(operation: { try await work.value }, onCancel: { work.cancel() })
        cached[code] = Cached(manifest: manifest, token: UUID().uuidString + UUID().uuidString, folder: folder)
        return manifest
    }
    public func send(_ manifest: Manifest, to peer: Peer) async throws {
        guard port > 0 else { throw FlowError.message("Máy chủ Wi-Fi chưa sẵn sàng.") }
        let destination = try await client.json(PeerConfig.self, base: peer.base, route: "api/config")
        guard destination.name == "FlowDrop", destination.deviceId != info.deviceId else { throw FlowError.message("Thiết bị nhận không hợp lệ.") }
        let token = UUID().uuidString.lowercased()
        var session = FlowSession(direction: "send", name: destination.deviceName, code: manifest.code, count: manifest.files.count, size: manifest.size)
        jobs[session.id] = session
        do {
            let request = OfferRequest(code: manifest.code, port: port, deviceId: info.deviceId, offerKey: destination.offerKey, statusToken: token)
            let reply = try await client.json(OfferReply.self, base: peer.base, route: "api/offers", method: "POST", body: JSONEncoder().encode(request))
            if reply.tracking == 1 { outgoing[session.id] = Outgoing(origin: peer.base, remoteID: reply.id, token: token) }
            else { session.state = "untracked"; session.error = "Cập nhật FlowDrop 1.8 trở lên ở máy nhận để xem kết quả."; jobs[session.id] = session }
        } catch { update(session.id) { $0.state = "failed"; $0.error = error.localizedDescription }; throw error }
    }
    public func refresh() async {
        expire()
        for (id, remote) in outgoing where jobs[id]?.terminal == false && !polling.contains(id) {
            polling.insert(id)
            Task { await self.poll(id: id, remote: remote) }
        }
    }
    private func poll(id: String, remote: Outgoing) async {
        defer { polling.remove(id) }
        do {
            let status = try await client.json(FlowSession.self, base: remote.origin, route: "api/offers/status", method: "POST", body: JSONEncoder().encode(StatusRequest(id: remote.remoteID, token: remote.token)))
            guard let local = jobs[id], !local.terminal else { return }
            guard status.count == local.count, status.size == local.size, status.bytes >= 0, status.bytes <= local.size, status.filesDone >= 0, status.filesDone <= local.count, ["pending", "accepted", "transferring", "completed", "rejected", "failed", "expired"].contains(status.state), status.state != "completed" || (status.bytes == local.size && status.filesDone == local.count) else { throw FlowError.message("Trạng thái từ máy nhận không hợp lệ.") }
            update(id) { value in value.state = status.state; value.bytes = status.bytes; value.filesDone = status.filesDone; value.currentName = status.currentName; value.startedAt = status.startedAt; value.finishedAt = status.finishedAt; value.error = status.error; value.connectionError = "" }
        } catch { if jobs[id]?.terminal == false { update(id) { $0.connectionError = "Mất kết nối · Đang thử lại"; $0.error = error.localizedDescription } } }
    }
    public func accept(_ id: String, photoCopy: (@Sendable (URL, String) async -> String?)? = nil) async {
        guard let offer = incoming[id], jobs[id]?.state == "pending" else { return }
        update(id) { $0.state = "accepted"; $0.startedAt = FlowProtocol.now }
        var bytes: Int64 = 0, done = 0
        do {
            for file in offer.manifest.files {
                try Task.checkCancellation()
                let offset = bytes, committed = done
                update(id) { $0.state = "transferring"; $0.currentName = file.name }
                let temp = try await client.download(base: offer.origin, code: offer.manifest.code, file: file) { count in
                    Task { await self.receiving(id, bytes: offset + count, done: committed, name: file.name) }
                }
                do {
                    try Task.checkCancellation()
                    let destination = try DiskFiles.commit(temp, name: file.name, directory: downloads)
                    var note: String? = nil
                    if let photoCopy { note = await photoCopy(destination, file.type) }
                    saved.insert(SavedFile(name: destination.lastPathComponent, path: destination.path, size: file.size), at: 0)
                    saved = Array(saved.prefix(200)); try JSONEncoder().encode(saved).write(to: history, options: .atomic)
                    bytes += file.size; done += 1
                    update(id) { $0.bytes = bytes; $0.filesDone = done; if let note { $0.error = note } }
                } catch { try? FileManager.default.removeItem(at: temp); throw error }
            }
            guard bytes == offer.manifest.size, done == offer.manifest.files.count else { throw FlowError.message("Chưa lưu đủ file.") }
            try Task.checkCancellation()
            update(id) { $0.state = "completed"; $0.bytes = bytes; $0.filesDone = done; $0.currentName = "" }
        } catch { update(id) { $0.state = "failed"; $0.error = error.localizedDescription } }
    }
    private func receiving(_ id: String, bytes: Int64, done: Int, name: String) {
        guard let job = jobs[id], !job.terminal, bytes >= job.bytes, done >= job.filesDone else { return }
        update(id) { $0.state = "transferring"; $0.bytes = bytes; $0.filesDone = done; $0.currentName = name }
    }
    public func reject(_ id: String) { if jobs[id]?.state == "pending" { update(id) { $0.state = "rejected" } } }
    public func interrupted() { for (id, job) in jobs where !job.terminal { update(id) { $0.state = "failed"; $0.error = "Ứng dụng đã dừng trước khi xác nhận lưu đủ file. Giữ FlowDrop mở và gửi lại." } } }
    public func route(_ request: HTTPRequest) async -> HTTPReply {
        expire()
        do {
            if !["GET", "HEAD"].contains(request.method), request.headers["origin"] != nil { return .error("Không cho phép yêu cầu từ trang web.", status: 403) }
            if request.method == "GET", request.path == "/api/config" { return try .json(info) }
            if request.method == "POST", request.path == "/api/offers" {
                let offered = try JSONDecoder().decode(OfferRequest.self, from: request.body)
                guard offered.offerKey == info.offerKey, offered.deviceId != info.deviceId, FlowProtocol.validCode(offered.code), FlowProtocol.validID(offered.statusToken), (1...65535).contains(offered.port), IPv4.valid(request.address) else { return .error("Yêu cầu gửi không hợp lệ.", status: 403) }
                guard incoming.keys.filter({ jobs[$0]?.terminal == false }).count < 20 else { return .error("Đang có nhiều phiên chờ nhận.", status: 429) }
                let origin = URL(string: "http://\(request.address):\(offered.port)")!
                let source = try await client.json(PeerConfig.self, base: origin, route: "api/config")
                guard source.name == "FlowDrop", source.deviceId == offered.deviceId else { return .error("Chưa xác minh được máy gửi.", status: 403) }
                let manifest = try await client.json(Manifest.self, base: origin, route: "api/transfers/" + offered.code); try manifest.validate()
                for (id, old) in incoming where old.origin == origin && old.manifest.code == offered.code && old.statusToken == offered.statusToken && jobs[id]?.terminal == false { return try .json(OfferReply(id: id, state: jobs[id]!.state, tracking: 1)) }
                let job = FlowSession(direction: "receive", name: source.deviceName, code: manifest.code, count: manifest.files.count, size: manifest.size)
                incoming[job.id] = Incoming(origin: origin, manifest: manifest, statusToken: offered.statusToken); jobs[job.id] = job
                return try .json(OfferReply(id: job.id, state: "pending", tracking: 1), status: 201)
            }
            if request.method == "POST", request.path == "/api/offers/status" {
                let asked = try JSONDecoder().decode(StatusRequest.self, from: request.body)
                guard let offer = incoming[asked.id], offer.statusToken == asked.token, let status = jobs[asked.id] else { return .error("Không có quyền xem phiên.", status: 403) }
                return try .json(status)
            }
            let parts = request.path.split(separator: "/").map(String.init)
            if parts.count >= 3, parts[0] == "api", parts[1] == "transfers", let item = cached[parts[2]] {
                if parts.count == 3, request.method == "GET" { return try .json(item.manifest) }
                if parts.count == 3, request.method == "DELETE" {
                    guard request.headers["x-upload-token"] == item.token else { return .error("Không có quyền thu hồi.", status: 403) }
                    try? FileManager.default.removeItem(at: item.folder); cached.removeValue(forKey: parts[2]); return try .json(["ok": true])
                }
                if parts.count == 5, parts[3] == "files", request.method == "GET", let file = item.manifest.files.first(where: { $0.id == parts[4] }) {
                    let url = item.folder.appendingPathComponent(file.id)
                    guard (try? DiskFiles.size(url)) == file.size else { return .error("File tạm không còn khả dụng.", status: 404) }
                    return HTTPReply(status: 200, body: .file(url, file.size, file.name))
                }
            }
            return .error("Không tìm thấy chức năng hoặc mã đã hết hạn.", status: 404)
        } catch { return .error(error.localizedDescription, status: 400) }
    }
}
public enum IPv4 {
    public static func valid(_ value: String) -> Bool { let parts = value.split(separator: ".", omittingEmptySubsequences: false); return parts.count == 4 && parts.allSatisfy { part in guard let value = Int(part) else { return false }; return (0...255).contains(value) && String(value) == String(part) } }
}
