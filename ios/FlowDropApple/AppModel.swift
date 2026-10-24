import SwiftUI
import UIKit
import UniformTypeIdentifiers
import Photos

@MainActor final class AppModel: ObservableObject {
    @Published var peers: [Peer] = []
    @Published var selectedPeer: String?
    @Published var files: [URL] = []
    @Published var sessions: [FlowSession] = []
    @Published var pending: [FlowSession] = []
    @Published var saved: [SavedFile] = []
    @Published var status = "Đang khởi động…"
    @Published var error = ""
    @Published var busy = false
    @Published var running = false
    @Published var preparation: Double = 0
    @Published var name: String
    @Published var photos: Bool { didSet { UserDefaults.standard.set(photos, forKey: "copyPhotos") } }
    private let store: HostStore, host: HTTPHost, discovery = Discovery()
    private var tick: Task<Void, Never>?, operations: [UUID: Task<Void, Never>] = [:], startup: Task<Void, Never>?
    private var backgroundTask = UIBackgroundTaskIdentifier.invalid
    init() throws {
        let defaults = UserDefaults.standard
        let id = defaults.string(forKey: "deviceId") ?? UUID().uuidString.lowercased(); defaults.set(id, forKey: "deviceId")
        name = defaults.string(forKey: "deviceName") ?? UIDevice.current.model; photos = defaults.bool(forKey: "copyPhotos")
        let fm = FileManager.default
        let documents = fm.urls(for: .documentDirectory, in: .userDomainMask)[0]
        let cache = fm.urls(for: .cachesDirectory, in: .userDomainMask)[0].appendingPathComponent("FlowDrop", isDirectory: true)
        store = try HostStore(root: cache, downloads: documents, config: PeerConfig(deviceName: name, platform: UIDevice.current.userInterfaceIdiom == .pad ? "ipados" : "ios", deviceId: id))
        host = HTTPHost(store: store)
        discovery.onPeers = { [weak self] peers in self?.peers = peers }
        discovery.onError = { [weak self] text in self?.error = text }
    }
    func activate() {
        guard startup == nil, !running else { return }
        startup = Task {
            defer { startup = nil }
            do {
                let port = try await host.start()
                guard !Task.isCancelled else { host.stop(); return }
                currentPort = port; await store.configure(port: port)
                discovery.start(config: await store.configuration(), port: port)
                running = true; status = "Sẵn sàng · Mở FlowDrop trên thiết bị cùng Wi-Fi"
                tick?.cancel(); tick = Task { while !Task.isCancelled { await store.refresh(); await update(); try? await Task.sleep(nanoseconds: 700_000_000) } }
            } catch { self.error = "Không mở được kết nối Wi-Fi: " + error.localizedDescription }
        }
    }
    func background() {
        // iOS only grants a short grace period. Stop honestly when it expires.
        guard backgroundTask == .invalid else { return }
        backgroundTask = UIApplication.shared.beginBackgroundTask(withName: "FlowDrop transfer") { [weak self] in Task { @MainActor in self?.suspend() } }
        if backgroundTask == .invalid { suspend() }
    }
    func foreground() { if backgroundTask != .invalid { UIApplication.shared.endBackgroundTask(backgroundTask); backgroundTask = .invalid }; activate() }
    private func suspend() {
        startup?.cancel(); tick?.cancel(); tick = nil; operations.values.forEach { $0.cancel() }; operations.removeAll()
        discovery.stop(); host.stop(); running = false; busy = false
        Task { await store.interrupted(); await update() }
        if backgroundTask != .invalid { UIApplication.shared.endBackgroundTask(backgroundTask); backgroundTask = .invalid }
        status = "Tạm dừng khi chạy nền · Mở FlowDrop để tiếp tục tìm thiết bị"
    }
    func update() async {
        let snapshot = await store.snapshot(); sessions = snapshot.sessions; pending = snapshot.pending; saved = snapshot.saved
        UIApplication.shared.isIdleTimerDisabled = busy || sessions.contains { !$0.terminal }
    }
    func rename() {
        name = String(name.trimmingCharacters(in: .whitespacesAndNewlines).prefix(100)); if name.isEmpty { name = UIDevice.current.model }
        UserDefaults.standard.set(name, forKey: "deviceName")
        Task { await store.rename(name); if running { discovery.start(config: await store.configuration(), port: currentPort) } }
    }
    private var currentPort = 0
    func rescan() { discovery.rescan() }
    func send() {
        guard !busy, running, let peer = peers.first(where: { $0.id == selectedPeer }), !files.isEmpty else { return }
        let urls = files, id = UUID(); busy = true; preparation = 0; status = "Đang chuẩn bị file…"
        operations[id] = Task {
            defer { busy = false; operations.removeValue(forKey: id) }
            let access = urls.map { ($0, $0.startAccessingSecurityScopedResource()) }
            defer { for (url, granted) in access where granted { url.stopAccessingSecurityScopedResource() } }
            do {
                let sources = try urls.map { url -> FileSource in
                    let content = try url.resourceValues(forKeys: [.contentTypeKey]).contentType
                    return FileSource(url: url, name: url.lastPathComponent, size: try DiskFiles.size(url), type: content?.preferredMIMEType ?? "application/octet-stream")
                }
                let manifest = try await store.prepare(sources) { [weak self] bytes, total, name in Task { @MainActor in self?.preparation = total > 0 ? Double(bytes) / Double(total) : 1; self?.status = "Đang chuẩn bị · " + name } }
                try Task.checkCancellation(); try await store.send(manifest, to: peer)
                status = "Đã gửi yêu cầu · Chấp nhận trên máy nhận"; files = []; await update()
            } catch { self.error = error.localizedDescription; status = "Chưa gửi được. Bạn có thể thử lại." }
        }
    }
    func accept(_ session: FlowSession) {
        let id = UUID(), copyPhotos = photos
        operations[id] = Task {
            defer { operations.removeValue(forKey: id) }
            let photoHandler: (@Sendable (URL, String) async -> String?)? = copyPhotos ? { url, type in await PhotoLibrary.copy(url, type: type) } : nil
            await store.accept(session.id, photoCopy: photoHandler)
            await update()
        }
    }
    func reject(_ session: FlowSession) { Task { await store.reject(session.id); await update() } }
}

enum PhotoLibrary {
    static func copy(_ url: URL, type: String) async -> String? {
        guard type.hasPrefix("image/") || type.hasPrefix("video/") else { return nil }
        guard await PHPhotoLibrary.requestAuthorization(for: .addOnly) == .authorized else { return "Đã lưu trong Tệp/FlowDrop; chưa có quyền thêm vào Ảnh." }
        do {
            try await PHPhotoLibrary.shared().performChanges {
                if type.hasPrefix("image/") { PHAssetChangeRequest.creationRequestForAssetFromImage(atFileURL: url) }
                else { PHAssetChangeRequest.creationRequestForAssetFromVideo(atFileURL: url) }
            }
            return nil
        } catch { return "Đã lưu trong Tệp/FlowDrop; không thêm được vào Ảnh: " + error.localizedDescription }
    }
}
