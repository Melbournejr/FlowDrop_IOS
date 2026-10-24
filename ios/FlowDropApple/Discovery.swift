import Foundation
import Darwin

/// Standard Bonjour works with Windows/Android without a restricted multicast entitlement.
// Foundation's Objective-C delegates lack actor annotations. All these services
// are scheduled on the main run loop, so their callbacks run on the main actor.
@MainActor final class Discovery: NSObject, @preconcurrency NetServiceBrowserDelegate, @preconcurrency NetServiceDelegate {
    var onPeers: ([Peer]) -> Void = { _ in }, onError: (String) -> Void = { _ in }
    private let browser = NetServiceBrowser(), client = HTTPClient()
    private var publisher: NetService?, services: [String: NetService] = [:], resolving: Set<String> = []
    private var peers: [String: Peer] = [:], serviceIDs: [String: String] = [:], seen: [String: Date] = [:]
    private var checks: [String: Task<Void, Never>] = [:], timer: Timer?, ownID = "", generation = UUID()
    override init() {
        super.init()
        browser.delegate = self; browser.includesPeerToPeer = false
        browser.schedule(in: .main, forMode: .common)
    }
    func start(config: PeerConfig, port: Int) {
        stop(); ownID = config.deviceId
        let service = NetService(domain: "local.", type: "_flowdrop._tcp.", name: "FlowDrop - " + String(config.deviceName.prefix(18)) + " " + String(ownID.suffix(6)), port: Int32(port))
        service.delegate = self; service.includesPeerToPeer = false
        service.schedule(in: .main, forMode: .common)
        service.setTXTRecord(NetService.data(fromTXTRecord: ["app": Data("flowdrop".utf8), "protocol": Data("1".utf8), "id": Data(ownID.utf8), "platform": Data(config.platform.utf8), "version": Data(config.version.utf8), "direct": Data("1".utf8)]))
        publisher = service; service.publish()
        browser.searchForServices(ofType: "_flowdrop._tcp.", inDomain: "local.")
        timer = Timer.scheduledTimer(withTimeInterval: 12, repeats: true) { [weak self] _ in Task { @MainActor in self?.rescan() } }
    }
    func stop() {
        generation = UUID(); timer?.invalidate(); timer = nil; browser.stop(); publisher?.stop(); publisher?.remove(from: .main, forMode: .common); publisher = nil
        for service in services.values { service.stop(); service.remove(from: .main, forMode: .common) }; services.removeAll(); resolving.removeAll()
        checks.values.forEach { $0.cancel() }; checks.removeAll(); peers.removeAll(); serviceIDs.removeAll(); seen.removeAll(); emit()
    }
    private func key(_ service: NetService) -> String { service.name + service.type + service.domain }
    private func emit() { onPeers(peers.values.sorted { $0.name.localizedCaseInsensitiveCompare($1.name) == .orderedAscending }) }
    func rescan() {
        for (id, date) in seen where Date().timeIntervalSince(date) > 40 { seen.removeValue(forKey: id); peers.removeValue(forKey: id) }
        for service in services.values { resolve(service) }; emit()
    }
    private func resolve(_ service: NetService) {
        let k = key(service)
        guard !resolving.contains(k), checks[k] == nil else { return }
        resolving.insert(k); service.delegate = self; service.resolve(withTimeout: 5)
    }
    func netServiceBrowser(_ browser: NetServiceBrowser, didFind service: NetService, moreComing: Bool) {
        service.schedule(in: .main, forMode: .common)
        services[key(service)] = service; resolve(service)
    }
    func netServiceBrowser(_ browser: NetServiceBrowser, didRemove service: NetService, moreComing: Bool) {
        let k = key(service)
        if let removed = services.removeValue(forKey: k) { removed.stop(); removed.remove(from: .main, forMode: .common) }
        resolving.remove(k); checks.removeValue(forKey: k)?.cancel()
        if let id = serviceIDs.removeValue(forKey: k), !serviceIDs.values.contains(id) { peers.removeValue(forKey: id); seen.removeValue(forKey: id); emit() }
    }
    func netServiceBrowser(_ browser: NetServiceBrowser, didNotSearch errorDict: [String: NSNumber]) { onError("Chưa tìm được thiết bị. Cho phép Mạng cục bộ trong Cài đặt → FlowDrop rồi thử lại.") }
    func netService(_ sender: NetService, didNotPublish errorDict: [String: NSNumber]) { onError("Chưa phát được tín hiệu FlowDrop trên Wi-Fi. Thử mở lại ứng dụng.") }
    func netService(_ sender: NetService, didNotResolve errorDict: [String: NSNumber]) { resolving.remove(key(sender)) }
    func netServiceDidResolveAddress(_ sender: NetService) {
        let k = key(sender); resolving.remove(k)
        guard services[k] === sender, sender.port > 0 else { return }
        let txt = sender.txtRecordData().map(NetService.dictionary(fromTXTRecord:)) ?? [:]
        if txt["id"] == Data(ownID.utf8) { return }
        let addresses = (sender.addresses ?? []).compactMap { data -> String? in
            data.withUnsafeBytes { raw in
                guard raw.count >= MemoryLayout<sockaddr_in>.size, raw.loadUnaligned(as: sockaddr.self).sa_family == sa_family_t(AF_INET) else { return nil }
                var address = raw.loadUnaligned(as: sockaddr_in.self).sin_addr
                var output = [CChar](repeating: 0, count: Int(INET_ADDRSTRLEN))
                guard inet_ntop(AF_INET, &address, &output, socklen_t(INET_ADDRSTRLEN)) != nil else { return nil }
                return String(cString: output)
            }
        }.filter { !$0.hasPrefix("127.") && $0 != "0.0.0.0" }
        guard !addresses.isEmpty, checks[k] == nil else { return }
        let epoch = generation, port = sender.port
        checks[k] = Task { [weak self] in
            guard let self else { return }
            defer { if self.generation == epoch { self.checks.removeValue(forKey: k) } }
            for address in addresses {
                guard !Task.isCancelled else { return }
                let base = URL(string: "http://\(address):\(port)")!
                guard let config = try? await self.client.json(PeerConfig.self, base: base, route: "api/config"), config.name == "FlowDrop", config.deviceId != self.ownID, config.direct == 1 else { continue }
                guard self.generation == epoch, self.services[k] === sender, !Task.isCancelled else { return }
                self.serviceIDs[k] = config.deviceId; self.peers[config.deviceId] = Peer(config: config, base: base); self.seen[config.deviceId] = Date(); self.emit(); return
            }
        }
    }
}
