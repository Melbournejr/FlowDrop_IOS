#if canImport(Network)
import Foundation
import Network

public final class HTTPHost: @unchecked Sendable {
    private let queue = DispatchQueue(label: "FlowDrop.HTTP"), store: HostStore
    private var listener: NWListener?, connections: [UUID: HTTPConnection] = [:]
    public init(store: HostStore) { self.store = store }
    public func start() async throws -> Int {
        try await withCheckedThrowingContinuation { continuation in
            queue.async {
                do {
                    let parameters = NWParameters.tcp
                    parameters.includePeerToPeer = false; parameters.prohibitedInterfaceTypes = [.cellular]
                    let listener = try NWListener(using: parameters, on: .any)
                    self.listener = listener
                    var answered = false
                    listener.stateUpdateHandler = { state in
                        switch state {
                        case .ready:
                            if !answered { answered = true; continuation.resume(returning: Int(listener.port!.rawValue)) }
                        case .failed(let error):
                            if !answered { answered = true; continuation.resume(throwing: error) }; listener.cancel()
                        case .cancelled:
                            if !answered { answered = true; continuation.resume(throwing: CancellationError()) }
                        default: break
                        }
                    }
                    listener.newConnectionHandler = { connection in
                        let id = UUID()
                        let session = HTTPConnection(connection, queue: self.queue, store: self.store) { [weak self] in self?.connections.removeValue(forKey: id) }
                        self.connections[id] = session; session.start()
                    }
                    listener.start(queue: self.queue)
                } catch { continuation.resume(throwing: error) }
            }
        }
    }
    public func stop() {
        queue.async { self.listener?.cancel(); self.listener = nil; let old = Array(self.connections.values); self.connections.removeAll(); old.forEach { $0.close() } }
    }
}
// Mutable state is confined to HTTPHost.queue. Tasks only read the immutable
// store/queue references, then dispatch the reply back onto that same queue.
private final class HTTPConnection: @unchecked Sendable {
    let connection: NWConnection, queue: DispatchQueue, store: HostStore, finished: () -> Void
    var parser = HTTPParser(), file: FileHandle?, remaining: Int64 = 0, timeout: DispatchWorkItem?, closed = false
    init(_ connection: NWConnection, queue: DispatchQueue, store: HostStore, finished: @escaping () -> Void) { self.connection = connection; self.queue = queue; self.store = store; self.finished = finished }
    func start() {
        connection.stateUpdateHandler = { [weak self] state in if case .failed = state { self?.close() }; if case .cancelled = state { self?.close() } }
        connection.start(queue: queue); touch(); read()
    }
    func touch() { timeout?.cancel(); let work = DispatchWorkItem { [weak self] in self?.close() }; timeout = work; queue.asyncAfter(deadline: .now() + 60, execute: work) }
    func close() { guard !closed else { return }; closed = true; timeout?.cancel(); try? file?.close(); file = nil; connection.cancel(); finished() }
    func read() {
        connection.receive(minimumIncompleteLength: 1, maximumLength: 65_536) { [weak self] data, _, complete, error in
            guard let self, !self.closed else { return }
            do {
                if let data, !data.isEmpty {
                    self.touch()
                    var address = ""
                    if case .hostPort(let host, _) = self.connection.endpoint {
                        address = "\(host)"; if address.hasPrefix("::ffff:") { address = String(address.dropFirst(7)) }
                    }
                    if let request = try self.parser.append(data, address: address) {
                        Task { let reply = await self.store.route(request); self.queue.async { self.reply(reply) } }; return
                    }
                }
                if error != nil || complete { self.close() } else { self.read() }
            } catch { self.reply(.error(error.localizedDescription, status: 400)) }
        }
    }
    func reply(_ value: HTTPReply) {
        guard !closed else { return }
        var response = value
        if case .file(let url, _, _) = response.body { do { file = try FileHandle(forReadingFrom: url) } catch { response = .error("Không mở được file.", status: 404) } }
        let size: Int64, type: String, bytes: Data?
        switch response.body {
        case .bytes(let data): size = Int64(data.count); type = "application/json; charset=utf-8"; bytes = data
        case .file(_, let length, _): size = length; type = "application/octet-stream"; bytes = nil; remaining = length
        }
        let header = "HTTP/1.1 \(response.status) Response\r\nContent-Length: \(size)\r\nContent-Type: \(type)\r\nConnection: close\r\nCache-Control: no-store\r\nX-Content-Type-Options: nosniff\r\n\r\n"
        var initial = Data(header.utf8); if let bytes { initial.append(bytes) }
        touch()
        connection.send(content: initial, completion: .contentProcessed { [weak self] error in
            guard let self else { return }; if error != nil || bytes != nil { self.close() } else { self.sendFile() }
        })
    }
    func sendFile() {
        guard !closed else { return }
        guard remaining > 0 else { close(); return }
        do {
            guard let data = try file?.read(upToCount: Int(min(remaining, 65_536))), !data.isEmpty else { close(); return }
            remaining -= Int64(data.count); touch()
            connection.send(content: data, completion: .contentProcessed { [weak self] error in if error != nil { self?.close() } else { self?.sendFile() } })
        } catch { close() }
    }
}
#endif
