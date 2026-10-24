import SwiftUI

@main struct FlowDropApp: App {
    @StateObject private var bootstrap = Bootstrap()
    @Environment(\.scenePhase) private var phase
    var body: some Scene {
        WindowGroup {
            Group {
                if let model = bootstrap.model { RootView().environmentObject(model) }
                else { VStack(spacing: 18) { Text("Chưa mở được FlowDrop").font(.title2); Text(bootstrap.error); Button("Thử lại") { bootstrap.retry() } }.padding() }
            }.preferredColorScheme(.dark).tint(Theme.mint)
                .onAppear { bootstrap.model?.foreground() }
                .onChange(of: phase) { value in
                    if value == .active { bootstrap.model?.foreground() }
                    if value == .background { bootstrap.model?.background() }
                }
        }
    }
}
@MainActor final class Bootstrap: ObservableObject {
    @Published var model: AppModel?
    @Published var error = ""
    init() { retry() }
    func retry() { do { model = try AppModel(); error = ""; model?.foreground() } catch { self.error = error.localizedDescription } }
}
enum Theme {
    static let background = Color(red: 0.035, green: 0.055, blue: 0.09)
    static let card = Color(red: 0.075, green: 0.105, blue: 0.15)
    static let mint = Color(red: 0.29, green: 0.9, blue: 0.67)
}
struct RootView: View {
    @EnvironmentObject var model: AppModel
    var body: some View {
        TabView {
            DevicesView().tabItem { Label("Thiết bị", systemImage: "wifi") }
            SessionsView().tabItem { Label("Phiên truyền", systemImage: "arrow.up.arrow.down") }.badge(model.pending.count)
            SavedFilesView().tabItem { Label("Đã nhận", systemImage: "folder") }
            PreferencesView().tabItem { Label("Cài đặt", systemImage: "gearshape") }
        }
        .alert("FlowDrop", isPresented: Binding(get: { !model.error.isEmpty }, set: { if !$0 { model.error = "" } })) { Button("Đóng", role: .cancel) { model.error = "" } } message: { Text(model.error) }
    }
}
struct Screen<Content: View>: View {
    let title: String
    let content: () -> Content
    init(title: String, @ViewBuilder content: @escaping () -> Content) { self.title = title; self.content = content }
    var body: some View {
        NavigationStack {
            ScrollView { VStack(alignment: .leading, spacing: 20, content: content).frame(maxWidth: 900).padding(20).frame(maxWidth: .infinity) }
                .background(Theme.background).navigationTitle(title)
        }
    }
}
struct Panel<Content: View>: View {
    let content: () -> Content
    init(@ViewBuilder content: @escaping () -> Content) { self.content = content }
    var body: some View { VStack(alignment: .leading, spacing: 14, content: content).frame(maxWidth: .infinity, alignment: .leading).padding(18).background(Theme.card, in: RoundedRectangle(cornerRadius: 20)) }
}
struct DevicesView: View {
    @EnvironmentObject var model: AppModel
    @State private var importer = false
    var body: some View {
        Screen(title: "FlowDrop.") {
            Label(model.running ? "Thiết bị cùng Wi-Fi" : "Đang mở kết nối", systemImage: "dot.radiowaves.left.and.right").foregroundStyle(Theme.mint)
            Text(model.status).font(.subheadline).foregroundStyle(.secondary)
            Panel {
                HStack { Text("Gửi đến").font(.title3.bold()); Spacer(); Button { model.rescan() } label: { Image(systemName: "arrow.clockwise") }.accessibilityLabel("Tìm lại thiết bị") }
                if model.peers.isEmpty {
                    Image(systemName: "wifi.circle").font(.system(size: 44)).foregroundStyle(Theme.mint).frame(maxWidth: .infinity)
                    Text("Đang tìm thiết bị…").font(.headline)
                    Text("Mở FlowDrop trên thiết bị nhận, dùng chung Wi-Fi và cho phép Mạng cục bộ. Máy tính và Android cần FlowDrop 1.9 trở lên.").font(.subheadline).foregroundStyle(.secondary)
                }
                ForEach(model.peers) { peer in
                    Button { model.selectedPeer = peer.id } label: {
                        HStack(spacing: 14) {
                            Image(systemName: peer.platform == "windows" ? "desktopcomputer" : peer.platform == "ipados" ? "ipad" : "iphone").font(.title2).frame(width: 34)
                            VStack(alignment: .leading) { Text(peer.name).font(.headline); Text(peer.platform).font(.caption).foregroundStyle(.secondary) }
                            Spacer(); Image(systemName: model.selectedPeer == peer.id ? "checkmark.circle.fill" : "circle")
                        }.padding(14).background(Theme.background, in: RoundedRectangle(cornerRadius: 14))
                    }.buttonStyle(.plain).foregroundStyle(model.selectedPeer == peer.id ? Theme.mint : .white)
                }
            }
            Panel {
                HStack { Text("File muốn gửi").font(.title3.bold()); Spacer(); Text("\(model.files.count) file").foregroundStyle(.secondary) }
                Button { importer = true } label: { Label("Chọn file", systemImage: "plus").frame(maxWidth: .infinity).padding(8) }.buttonStyle(.bordered).disabled(model.busy)
                ForEach(Array(model.files.enumerated()), id: \.offset) { _, url in Text(url.lastPathComponent).font(.subheadline).lineLimit(1) }
                if model.busy { ProgressView(value: model.preparation).tint(Theme.mint) }
                Button { model.send() } label: { Label(model.busy ? "Đang chuẩn bị…" : "Gửi file", systemImage: "paperplane.fill").font(.headline).frame(maxWidth: .infinity).padding(9) }.buttonStyle(.borderedProminent).foregroundStyle(Theme.background).disabled(model.busy || !model.running || model.files.isEmpty || !model.peers.contains(where: { $0.id == model.selectedPeer }))
                Text("Giữ FlowDrop mở ở cả hai thiết bị cho đến khi phiên báo hoàn tất.").font(.caption).foregroundStyle(.secondary)
            }
            if !model.pending.isEmpty { Text("Có \(model.pending.count) yêu cầu nhận file. Mở tab Phiên truyền để chấp nhận.").foregroundStyle(Theme.mint) }
        }
        .fileImporter(isPresented: $importer, allowedContentTypes: [.item], allowsMultipleSelection: true) { result in
            switch result { case .success(let urls): model.files = urls; case .failure(let error): model.error = error.localizedDescription }
        }
    }
}
struct SessionsView: View {
    @EnvironmentObject var model: AppModel
    var body: some View {
        Screen(title: "Phiên truyền") {
            if model.sessions.isEmpty { Panel { Label("Chưa có phiên truyền", systemImage: "arrow.up.arrow.down.circle").font(.headline); Text("Tiến độ gửi và nhận sẽ xuất hiện tại đây.").foregroundStyle(.secondary) } }
            ForEach(model.sessions) { session in SessionCard(session: session) }
        }
    }
}
struct SessionCard: View {
    @EnvironmentObject var model: AppModel
    let session: FlowSession
    var body: some View {
        Panel {
            HStack {
                Image(systemName: session.direction == "send" ? "arrow.up.right.circle.fill" : "arrow.down.left.circle.fill").font(.title).foregroundStyle(Theme.mint)
                VStack(alignment: .leading) { Text(session.direction == "send" ? "Gửi đến" : "Nhận từ").font(.caption).foregroundStyle(.secondary); Text(session.name).font(.headline) }
                Spacer(); Text("\(Int(session.fraction * 100))%").monospacedDigit().font(.title3.bold())
            }
            Text(session.label).font(.subheadline).foregroundStyle(session.state == "failed" ? .orange : Theme.mint)
            ProgressView(value: session.fraction).tint(Theme.mint)
            Text("\(ByteCountFormatter.string(fromByteCount: session.bytes, countStyle: .file)) / \(ByteCountFormatter.string(fromByteCount: session.size, countStyle: .file)) · \(session.filesDone)/\(session.count) file").font(.caption).foregroundStyle(.secondary)
            if !session.currentName.isEmpty { Text(session.currentName).font(.caption).lineLimit(2) }
            if !session.error.isEmpty { Text(session.error).font(.caption).foregroundStyle(.orange) }
            if session.direction == "receive" && session.state == "pending" {
                HStack { Button("Từ chối", role: .destructive) { model.reject(session) }.buttonStyle(.bordered); Spacer(); Button("Nhận và lưu") { model.accept(session) }.buttonStyle(.borderedProminent).foregroundStyle(Theme.background) }
            }
        }
    }
}
struct SavedFilesView: View {
    @EnvironmentObject var model: AppModel
    var body: some View {
        Screen(title: "File đã nhận") {
            Text("Tự động lưu trong Tệp → Trên iPhone/iPad của tôi → FlowDrop.").font(.subheadline).foregroundStyle(.secondary)
            if model.saved.isEmpty { Panel { Label("Chưa có file", systemImage: "folder"); Text("File chỉ báo hoàn tất sau khi lưu thành công.").font(.subheadline).foregroundStyle(.secondary) } }
            ForEach(model.saved) { file in
                Panel {
                    Label(file.name, systemImage: "doc").font(.headline)
                    Text(ByteCountFormatter.string(fromByteCount: file.size, countStyle: .file)).font(.caption).foregroundStyle(.secondary)
                    if FileManager.default.fileExists(atPath: file.url.path) { ShareLink(item: file.url) { Label("Mở / Chia sẻ", systemImage: "square.and.arrow.up") } }
                    else { Text("File đã được di chuyển hoặc xóa trong Tệp.").font(.caption).foregroundStyle(.secondary) }
                }
            }
        }
    }
}
struct PreferencesView: View {
    @EnvironmentObject var model: AppModel
    var body: some View {
        Screen(title: "Cài đặt") {
            Panel { Text("Tên thiết bị").font(.headline); TextField("Tên iPhone/iPad", text: $model.name).textFieldStyle(.roundedBorder).onSubmit { model.rename() }; Button("Lưu tên") { model.rename() } }
            Panel { Toggle("Thêm ảnh và video vào Ảnh", isOn: $model.photos); Text("Bản gốc luôn được lưu trong Tệp/FlowDrop. iOS sẽ hỏi quyền thêm vào thư viện Ảnh khi cần.").font(.caption).foregroundStyle(.secondary) }
            Panel {
                Label("Mạng cục bộ", systemImage: "wifi").font(.headline)
                Text("Cho phép FlowDrop truy cập Mạng cục bộ trong Cài đặt iOS. Hai thiết bị cần cùng Wi-Fi; Wi-Fi khách có thể chặn các thiết bị nhìn thấy nhau.").font(.subheadline).foregroundStyle(.secondary)
                Button("Mở cài đặt hệ thống") { if let url = URL(string: UIApplication.openSettingsURLString) { UIApplication.shared.open(url) } }
            }
            Text("FlowDrop iOS/iPadOS 1.0 · Bản phát triển\nTruyền trực tiếp trong LAN. Giữ ứng dụng mở khi truyền file.").font(.caption).foregroundStyle(.secondary)
        }
    }
}
