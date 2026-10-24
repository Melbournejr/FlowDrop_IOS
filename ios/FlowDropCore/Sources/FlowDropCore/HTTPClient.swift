import Foundation
#if canImport(FoundationNetworking)
import FoundationNetworking
#endif

private final class RedirectPolicy: NSObject, URLSessionTaskDelegate, @unchecked Sendable {
    func urlSession(_ session: URLSession, task: URLSessionTask, willPerformHTTPRedirection response: HTTPURLResponse, newRequest request: URLRequest, completionHandler: @escaping (URLRequest?) -> Void) { completionHandler(nil) }
}
public final class HTTPClient: @unchecked Sendable {
    private let policy: RedirectPolicy
    private let session: URLSession
    static func configuration() -> URLSessionConfiguration {
        let config = URLSessionConfiguration.ephemeral
        config.allowsCellularAccess = false
        config.timeoutIntervalForRequest = 120
        config.timeoutIntervalForResource = 7 * 24 * 3600
        config.httpCookieStorage = nil
        config.urlCredentialStorage = nil
        return config
    }
    public init() { let policy = RedirectPolicy(); self.policy = policy; session = URLSession(configuration: Self.configuration(), delegate: policy, delegateQueue: nil) }
    public func json<T: Decodable>(_ type: T.Type, base: URL, route: String, method: String = "GET", body: Data? = nil, token: String? = nil) async throws -> T {
        let root = try FlowProtocol.base(base)
        var request = URLRequest(url: root.appendingPathComponent(route))
        request.httpMethod = method; request.httpBody = body; request.timeoutInterval = 8
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        if let token { request.setValue(token, forHTTPHeaderField: "X-Upload-Token") }
        // Download JSON to a temporary file, so an oversized response cannot grow RAM without bound.
        let (temporary, response) = try await session.download(for: request)
        defer { try? FileManager.default.removeItem(at: temporary) }
        guard try DiskFiles.size(temporary) <= Int64(FlowProtocol.maxManifest), let http = response as? HTTPURLResponse else { throw FlowError.message("Phản hồi thiết bị quá lớn hoặc không hợp lệ.") }
        let data = try Data(contentsOf: temporary)
        guard (200..<300).contains(http.statusCode) else {
            let error = try? JSONDecoder().decode(APIError.self, from: data)
            throw FlowError.message(error?.error ?? "Thiết bị trả lỗi \(http.statusCode).")
        }
        return try JSONDecoder().decode(type, from: data)
    }
    public func download(base: URL, code: String, file: FlowFile, progress: @escaping @Sendable (Int64) -> Void) async throws -> URL {
        guard FlowProtocol.validCode(code), FlowProtocol.validID(file.id) else { throw FlowError.message("Mã hoặc ID file không hợp lệ.") }
        let url = try FlowProtocol.base(base).appendingPathComponent("api/transfers/\(code)/files/\(file.id)")
        let transfer = DownloadJob(expected: file.size, progress: progress)
        return try await withTaskCancellationHandler(operation: { try await transfer.run(url: url) }, onCancel: { transfer.cancel() })
    }
    private struct APIError: Decodable { var error: String }
}
private final class DownloadJob: NSObject, URLSessionDownloadDelegate, @unchecked Sendable {
    private let expected: Int64, progress: @Sendable (Int64) -> Void
    private let lock = NSLock()
    private var continuation: CheckedContinuation<URL, Error>?, session: URLSession?, task: URLSessionDownloadTask?, result: URL?, failure: Error?, cancelled = false
    init(expected: Int64, progress: @escaping @Sendable (Int64) -> Void) { self.expected = expected; self.progress = progress }
    func run(url: URL) async throws -> URL {
        try await withCheckedThrowingContinuation { continuation in
            lock.lock()
            if cancelled { lock.unlock(); continuation.resume(throwing: CancellationError()); return }
            self.continuation = continuation
            let session = URLSession(configuration: HTTPClient.configuration(), delegate: self, delegateQueue: nil); self.session = session
            let task = session.downloadTask(with: url); self.task = task; lock.unlock(); task.resume()
        }
    }
    func cancel() { lock.lock(); cancelled = true; let task = task; lock.unlock(); task?.cancel() }
    func urlSession(_ session: URLSession, downloadTask: URLSessionDownloadTask, didWriteData bytesWritten: Int64, totalBytesWritten: Int64, totalBytesExpectedToWrite: Int64) {
        if totalBytesWritten > expected { downloadTask.cancel(); return }; progress(totalBytesWritten)
    }
    func urlSession(_ session: URLSession, task: URLSessionTask, willPerformHTTPRedirection response: HTTPURLResponse, newRequest request: URLRequest, completionHandler: @escaping (URLRequest?) -> Void) { completionHandler(nil) }
    func urlSession(_ session: URLSession, downloadTask: URLSessionDownloadTask, didFinishDownloadingTo location: URL) {
        do {
            guard (downloadTask.response as? HTTPURLResponse)?.statusCode == 200, try DiskFiles.size(location) == expected else { throw FlowError.message("File tải chưa đủ hoặc dung lượng không khớp.") }
            let target = FileManager.default.temporaryDirectory.appendingPathComponent("flowdrop-" + UUID().uuidString + ".part")
            try FileManager.default.moveItem(at: location, to: target); result = target
        } catch { failure = error }
    }
    func urlSession(_ session: URLSession, task: URLSessionTask, didCompleteWithError error: Error?) {
        lock.lock(); let done = continuation; continuation = nil; lock.unlock()
        if let error = error ?? failure { if let result { try? FileManager.default.removeItem(at: result) }; done?.resume(throwing: error) }
        else if let result { progress(expected); done?.resume(returning: result) }
        else { done?.resume(throwing: FlowError.message("Chưa tải được file.")) }
        session.finishTasksAndInvalidate()
    }
}
