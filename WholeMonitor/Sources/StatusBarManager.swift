import SwiftUI
import AppKit
import Combine

class StatusBarManager: NSObject, NSPopoverDelegate {
    private var statusItem: NSStatusItem
    private var popover: NSPopover
    private var healthChecker: HealthChecker
    private var cancellables = Set<AnyCancellable>()

    override init() {
        statusItem = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
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
                systemSymbolName: "eye.fill",
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
        popover.contentViewController = VibrantHostingController(
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
            NSColor(hex: state.colorHex) ?? .systemGray
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
        restartCollectorScript()
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

/// Hosting controller with a live frosted-glass back: .popover material,
/// behind-window blending — the same house glass as Hermes Config Guardian.
/// The SwiftUI content stays transparent and floats on it.
final class VibrantHostingController<Content: View>: NSHostingController<Content> {
    override func loadView() {
        let effect = NSVisualEffectView()
        effect.material = .popover
        effect.blendingMode = .behindWindow
        effect.state = .active
        view = effect
    }
}

func restartCollectorScript() {
    let task = Process()
    task.executableURL = URL(fileURLWithPath: "/bin/bash")
    task.arguments = ["-c", "cd ~/Developer/whole && ./install-macos.sh"]
    try? task.run()
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
