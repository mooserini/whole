# WholeMonitor - Complete Source

A SwiftUI menu bar extra that monitors your local Whole workstream daemon.

## Architecture

- `WholeMonitorApp.swift` - App lifecycle, no dock icon (`LSUIElement`)
- `Models.swift` - Codable structs for `/health` and `/api/status` responses, plus health state enum
- `HealthChecker.swift` - Async polling service (every 30s), hits both endpoints, computes state
- `StatusBarManager.swift` - `NSStatusItem`, `NSPopover`, icon color updates, right-click menu
- `MonitorView.swift` - SwiftUI popover content: header, stats grid, action buttons

## State Logic

```
healthy  = collectorRunning AND last observation < 5 minutes ago
stale    = collectorRunning BUT last observation > 5 minutes ago  
down     = cannot connect OR collector not running
unknown  = connected but cannot determine state
```

---

## WholeMonitorApp.swift

```swift
import SwiftUI
import AppKit

@main
struct WholeMonitorApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) var appDelegate
    
    var body: some Scene {
        Settings {
            EmptyView()
        }
    }
}

class AppDelegate: NSObject, NSApplicationDelegate {
    var statusBarManager: StatusBarManager?
    
    func applicationDidFinishLaunching(_ notification: Notification) {
        statusBarManager = StatusBarManager()
    }
}
```

---

## Models.swift

```swift
import Foundation

struct WholeHealth: Codable {
    let collectorRunning: Bool?
    let accessibilityEnabled: Bool?
    let launchdRegistered: Bool?
    let processAlive: Bool?
    let trailFresh: Bool?
    let plistValid: Bool?
    let lastCheck: Date?
}

struct WholeStatus: Codable {
    let totalObservations: Int?
    let activeTimeLowerBound: String?
    let cleanCount: Int?
    let flaggedCount: Int?
    let collectorState: String?
    let lastObservationAt: String?
}

struct CombinedHealth {
    let state: HealthState
    let health: WholeHealth?
    let status: WholeStatus?
    let lastCheck: Date
    let error: String?
}

enum HealthState: String {
    case healthy = "healthy"
    case stale = "stale"
    case down = "down"
    case unknown = "unknown"
    
    var color: String {
        switch self {
        case .healthy: return "#34C759"
        case .stale: return "#FF9500"
        case .down: return "#FF3B30"
        case .unknown: return "#8E8E93"
        }
    }
    
    var icon: String {
        switch self {
        case .healthy: return "circle.fill"
        case .stale: return "exclamationmark.circle.fill"
        case .down: return "xmark.circle.fill"
        case .unknown: return "questionmark.circle.fill"
        }
    }
    
    var description: String {
        switch self {
        case .healthy: return "Collecting"
        case .stale: return "Stale"
        case .down: return "Offline"
        case .unknown: return "Checking..."
        }
    }
}
```

---

## HealthChecker.swift

```swift
import Foundation
import Combine

class HealthChecker: ObservableObject {
    @Published var combined: CombinedHealth?
    
    private var cancellables = Set<AnyCancellable>()
    private let baseURL = "http://127.0.0.1:39400"
    private let interval: TimeInterval
    
    init(pollInterval: TimeInterval = 30.0) {
        self.interval = pollInterval
        startPolling()
    }
    
    func startPolling() {
        Timer.publish(every: interval, on: .main, in: .common)
            .autoconnect()
            .sink { [weak self] _ in
                self?.check()
            }
            .store(in: &cancellables)
        
        check()
    }
    
    func check() {
        Task {
            await performCheck()
        }
    }
    
    private func performCheck() async {
        let health: WholeHealth? = await fetch(endpoint: "/health")
        let status: WholeStatus? = await fetch(endpoint: "/api/status")
        
        let now = Date()
        let state: HealthState
        var error: String? = nil
        
        if health == nil && status == nil {
            state = .down
            error = "Cannot connect to Whole at \(baseURL)"
        } else if let health = health {
            if health.collectorRunning == true {
                if let lastObs = status?.lastObservationAt,
                   let date = ISO8601DateFormatter().date(from: lastObs) {
                    let minutesSince = now.timeIntervalSince(date) / 60
                    if minutesSince > 5 {
                        state = .stale
                    } else {
                        state = .healthy
                    }
                } else {
                    state = .healthy
                }
            } else {
                state = .down
            }
        } else {
            state = .unknown
        }
        
        await MainActor.run {
            self.combined = CombinedHealth(
                state: state,
                health: health,
                status: status,
                lastCheck: now,
                error: error
            )
        }
    }
    
    private func fetch<T: Codable>(endpoint: String) async -> T? {
        guard let url = URL(string: baseURL + endpoint) else { return nil }
        
        var request = URLRequest(url: url)
        request.timeoutInterval = 5
        
        do {
            let (data, response) = try await URLSession.shared.data(for: request)
            guard let http = response as? HTTPURLResponse, http.statusCode == 200 else {
                return nil
            }
            return try JSONDecoder().decode(T.self, from: data)
        } catch {
            return nil
        }
    }
}
```

---

## StatusBarManager.swift

```swift
import SwiftUI
import AppKit
import Combine

class StatusBarManager: NSObject, NSPopoverDelegate {
    private var statusItem: NSStatusItem
    private var popover: NSPopover
    private var healthChecker: HealthChecker
    private var cancellables = Set<AnyCancellable>()
    
    override init() {
        statusItem = NSStatusBar.shared.statusItem(withLength: NSStatusItem.variableLength)
        popover = NSPopover()
        healthChecker = HealthChecker(pollInterval: 30.0)
        
        super.init()
        
        setupStatusItem()
        setupPopover()
        observeHealth()
    }
    
    private func setupStatusItem() {
        if let button = statusItem.button {
            button.image = NSImage(
                systemSymbolName: "circle.fill",
                accessibilityDescription: "Whole Monitor"
            )
            button.action = #selector(togglePopover)
            button.sendAction(on: [.leftMouseUp, .rightMouseUp])
            button.target = self
        }
    }
    
    private func setupPopover() {
        popover.contentSize = NSSize(width: 320, height: 380)
        popover.behavior = .transient
        popover.delegate = self
        popover.contentViewController = NSHostingController(
            rootView: MonitorView(healthChecker: healthChecker, manager: self)
        )
    }
    
    private func observeHealth() {
        healthChecker.$combined
            .receive(on: RunLoop.main)
            .sink { [weak self] combined in
                self?.updateIcon(for: combined)
            }
            .store(in: &cancellables)
    }
    
    private func updateIcon(for combined: CombinedHealth?) {
        guard let button = statusItem.button else { return }
        let state = combined?.state ?? .unknown
        let config = NSImage.SymbolConfiguration(paletteColors: [
            NSColor(hex: state.color) ?? .systemGray
        ])
        button.image = NSImage(
            systemSymbolName: state.icon,
            accessibilityDescription: state.description
        )?.withSymbolConfiguration(config)
        button.toolTip = "Whole: \(state.description)"
    }
    
    @objc private func togglePopover(_ sender: AnyObject?) {
        guard let event = NSApp.currentEvent else { return }
        
        if event.type == .rightMouseUp {
            showMenu()
        } else {
            if popover.isShown {
                closePopover()
            } else {
                showPopover()
            }
        }
    }
    
    private func showPopover() {
        if let button = statusItem.button {
            popover.show(relativeTo: button.bounds, of: button, preferredEdge: .minY)
        }
    }
    
    private func closePopover() {
        popover.performClose(nil)
    }
    
    private func showMenu() {
        let menu = NSMenu()
        
        menu.addItem(withTitle: "Open Dashboard", action: #selector(openDashboard), keyEquivalent: "")
        menu.addItem(withTitle: "Restart Collector", action: #selector(restartCollector), keyEquivalent: "")
        menu.addItem(withTitle: "Run Health Check", action: #selector(runHealthCheck), keyEquivalent: "")
        menu.addItem(NSMenuItem.separator())
        menu.addItem(withTitle: "Open Whole Folder", action: #selector(openWholeFolder), keyEquivalent: "")
        menu.addItem(NSMenuItem.separator())
        menu.addItem(withTitle: "Quit", action: #selector(quitApp), keyEquivalent: "q")
        
        for item in menu.items {
            item.target = self
        }
        
        statusItem.menu = menu
        statusItem.button?.performClick(nil)
        statusItem.menu = nil
    }
    
    @objc private func openDashboard() {
        if let url = URL(string: "http://127.0.0.1:39400") {
            NSWorkspace.shared.open(url)
        }
    }
    
    @objc private func restartCollector() {
        let task = Process()
        task.launchPath = "/bin/bash"
        task.arguments = ["-c", "cd ~/Developer/whole && make install-macos"]
        try? task.run()
    }
    
    @objc private func runHealthCheck() {
        healthChecker.check()
    }
    
    @objc private func openWholeFolder() {
        let home = FileManager.default.homeDirectoryForCurrentUser
        let url = home.appendingPathComponent("Developer/whole")
        NSWorkspace.shared.open(url)
    }
    
    @objc private func quitApp() {
        NSApplication.shared.terminate(nil)
    }
    
    func popoverShouldDetach(_ popover: NSPopover) -> Bool {
        return false
    }
}

extension NSColor {
    convenience init?(hex: String) {
        let trimmed = hex.trimmingCharacters(in: CharacterSet(charactersIn: "#"))
        guard trimmed.count == 6 else { return nil }
        
        var rgb: UInt64 = 0
        guard Scanner(string: trimmed).scanHexInt64(&rgb) else { return nil }
        
        self.init(
            red: CGFloat((rgb & 0xFF0000) >> 16) / 255.0,
            green: CGFloat((rgb & 0x00FF00) >> 8) / 255.0,
            blue: CGFloat(rgb & 0x0000FF) / 255.0,
            alpha: 1.0
        )
    }
}
```

---

## MonitorView.swift

```swift
import SwiftUI

struct MonitorView: View {
    @ObservedObject var healthChecker: HealthChecker
    weak var manager: StatusBarManager?
    
    var body: some View {
        VStack(spacing: 0) {
            header
            Divider()
            statsGrid
            Divider()
            actions
            Spacer(minLength: 8)
        }
        .frame(width: 320)
        .background(Color(NSColor.windowBackgroundColor))
    }
    
    private var header: some View {
        HStack(spacing: 12) {
            Image(systemName: healthChecker.combined?.state.icon ?? "questionmark.circle.fill")
                .font(.system(size: 28, weight: .semibold))
                .foregroundColor(colorForState)
            
            VStack(alignment: .leading, spacing: 2) {
                Text("WHOLE")
                    .font(.system(size: 13, weight: .bold))
                    .foregroundColor(.primary)
                
                Text(healthChecker.combined?.state.description ?? "Checking...")
                    .font(.system(size: 12, weight: .medium))
                    .foregroundColor(colorForState)
            }
            
            Spacer()
            
            if let last = healthChecker.combined?.lastCheck {
                Text(timeAgo(last))
                    .font(.system(size: 10))
                    .foregroundColor(.secondary)
            }
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 14)
    }
    
    private var statsGrid: some View {
        VStack(spacing: 10) {
            HStack(spacing: 10) {
                statCard(
                    label: "Observations",
                    value: formattedCount(healthChecker.combined?.status?.totalObservations),
                    icon: "doc.on.doc"
                )
                statCard(
                    label: "Active Time",
                    value: healthChecker.combined?.status?.activeTimeLowerBound ?? "--",
                    icon: "clock"
                )
            }
            
            HStack(spacing: 10) {
                statCard(
                    label: "Privacy Clean",
                    value: formattedCount(healthChecker.combined?.status?.cleanCount),
                    icon: "checkmark.shield"
                )
                statCard(
                    label: "Flagged",
                    value: formattedCount(healthChecker.combined?.status?.flaggedCount),
                    icon: "exclamationmark.shield"
                )
            }
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 12)
    }
    
    private var actions: some View {
        VStack(spacing: 6) {
            Button("Open Dashboard") {
                if let url = URL(string: "http://127.0.0.1:39400") {
                    NSWorkspace.shared.open(url)
                }
            }
            .buttonStyle(WholeButtonStyle())
            
            HStack(spacing: 6) {
                Button("Restart") {
                    let task = Process()
                    task.launchPath = "/bin/bash"
                    task.arguments = ["-c", "cd ~/Developer/whole && make install-macos"]
                    try? task.run()
                }
                .buttonStyle(WholeButtonStyle(secondary: true))
                
                Button("Refresh") {
                    healthChecker.check()
                }
                .buttonStyle(WholeButtonStyle(secondary: true))
            }
            
            if let error = healthChecker.combined?.error {
                Text(error)
                    .font(.system(size: 11))
                    .foregroundColor(.red)
                    .multilineTextAlignment(.center)
                    .padding(.horizontal, 12)
                    .padding(.top, 4)
            }
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 10)
    }
    
    private func statCard(label: String, value: String, icon: String) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack(spacing: 4) {
                Image(systemName: icon)
                    .font(.system(size: 11))
                    .foregroundColor(.secondary)
                Text(label)
                    .font(.system(size: 10, weight: .medium))
                    .foregroundColor(.secondary)
            }
            Text(value)
                .font(.system(size: 16, weight: .semibold))
                .foregroundColor(.primary)
                .lineLimit(1)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(10)
        .background(Color(NSColor.controlBackgroundColor))
        .cornerRadius(8)
    }
    
    private var colorForState: Color {
        guard let hex = healthChecker.combined?.state.color else { return .gray }
        if let nsColor = NSColor(hex: hex) {
            return Color(nsColor)
        }
        return .gray
    }
    
    private func formattedCount(_ count: Int?) -> String {
        guard let count = count else { return "--" }
        let formatter = NumberFormatter()
        formatter.numberStyle = .decimal
        return formatter.string(from: NSNumber(value: count)) ?? String(count)
    }
    
    private func timeAgo(_ date: Date) -> String {
        let interval = Date().timeIntervalSince(date)
        if interval < 60 { return "just now" }
        let mins = Int(interval / 60)
        if mins < 60 { return "\(mins)m ago" }
        let hours = mins / 60
        return "\(hours)h ago"
    }
}

struct WholeButtonStyle: ButtonStyle {
    var secondary: Bool = false
    
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.system(size: 12, weight: .medium))
            .padding(.vertical, 6)
            .frame(maxWidth: .infinity)
            .background(
                secondary
                ? Color(NSColor.controlBackgroundColor)
                : Color.accentColor.opacity(configuration.isPressed ? 0.7 : 1.0)
            )
            .foregroundColor(secondary ? .primary : .white)
            .cornerRadius(6)
            .opacity(configuration.isPressed ? 0.8 : 1.0)
    }
}
```

---

## Info.plist

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleDevelopmentRegion</key>
    <string>en</string>
    <key>CFBundleExecutable</key>
    <string>$(EXECUTABLE_NAME)</string>
    <key>CFBundleIdentifier</key>
    <string>com.mooserini.wholemonitor</string>
    <key>CFBundleInfoDictionaryVersion</key>
    <string>6.0</string>
    <key>CFBundleName</key>
    <string>WholeMonitor</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0</string>
    <key>CFBundleVersion</key>
    <string>1</string>
    <key>LSMinimumSystemVersion</key>
    <string>14.0</string>
    <key>LSUIElement</key>
    <true/>
</dict>
</plist>
```

## Build Notes

1. Create a new macOS App project in Xcode
2. Replace the generated files with these
3. Add `LSUIElement` to Info.plist (hides dock icon, no main menu)
4. Target macOS 14.0+
5. Build and run

The app assumes Whole runs at `127.0.0.1:39400` and your repo lives at `~/Developer/whole`. Adjust `HealthChecker.baseURL` and `StatusBarManager.restartCollector()` if your setup differs.
