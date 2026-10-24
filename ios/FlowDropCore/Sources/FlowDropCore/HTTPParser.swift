import Foundation

/// One request per connection; file payloads are served as streams, never collected here.
public struct HTTPParser {
    private var buffer = Data(), parsed: (String, String, [String: String], Int)?
    public init() {}
    public mutating func append(_ data: Data, address: String) throws -> HTTPRequest? {
        buffer.append(data)
        if parsed == nil {
            guard let end = buffer.range(of: Data("\r\n\r\n".utf8)) else {
                guard buffer.count <= 16_384 else { throw FlowError.message("Header quá lớn.") }; return nil
            }
            guard end.upperBound <= 16_384, let text = String(data: buffer[..<end.lowerBound], encoding: .utf8) else { throw FlowError.message("Header không hợp lệ.") }
            let lines = text.components(separatedBy: "\r\n"), first = lines[0].split(separator: " ")
            guard first.count == 3, first[2] == "HTTP/1.1" || first[2] == "HTTP/1.0", ["GET", "POST", "DELETE", "HEAD"].contains(String(first[0])), first[1].hasPrefix("/"), !first[1].contains("#") else { throw FlowError.message("Yêu cầu HTTP không hợp lệ.") }
            var headers: [String: String] = [:]
            for line in lines.dropFirst() {
                guard let colon = line.firstIndex(of: ":"), !line.hasPrefix(" "), !line.hasPrefix("\t") else { throw FlowError.message("Header không hợp lệ.") }
                let key = line[..<colon].lowercased(), value = line[line.index(after: colon)...].trimmingCharacters(in: .whitespaces)
                guard !key.isEmpty, key.utf8.allSatisfy({ (97...122).contains($0) || (48...57).contains($0) || $0 == 45 }), headers[key] == nil, value.rangeOfCharacter(from: .controlCharacters) == nil else { throw FlowError.message("Header trùng hoặc không hợp lệ.") }
                headers[key] = value
            }
            guard headers["transfer-encoding"] == nil else { throw FlowError.message("Không hỗ trợ chunked request.") }
            let lengthText = headers["content-length"] ?? "0"
            guard !lengthText.isEmpty, lengthText.utf8.allSatisfy({ (48...57).contains($0) }), let length = Int(lengthText), length <= FlowProtocol.maxManifest else { throw FlowError.message("Nội dung yêu cầu quá lớn.") }
            parsed = (String(first[0]), String(first[1].split(separator: "?", maxSplits: 1)[0]), headers, length)
            buffer.removeSubrange(..<end.upperBound)
        }
        guard let (method, path, headers, length) = parsed else { return nil }
        guard buffer.count <= length else { throw FlowError.message("Độ dài HTTP không khớp.") }
        guard buffer.count == length else { return nil }
        return HTTPRequest(method: method, path: path, headers: headers, body: buffer, address: address)
    }
}
