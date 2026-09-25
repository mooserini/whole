import Foundation

/// Login behavior for the Whole household, managed through user LaunchAgents
/// so nothing here depends on signing, notarization, or /Applications.
/// Two independent switches: the Monitor menubar pixel itself, and the
/// Whole frontmost collector it watches.
enum LoginItems {
    static let monitorLabel = "com.moosenberg.wholemonitor"
    static let collectorLabel = "com.moosenberg.whole-frontmost"

    private static var uid: String { String(getuid()) }
    private static var gui: String { "gui/\(uid)" }

    private static var monitorPlist: URL {
        FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent("Library/LaunchAgents/\(monitorLabel).plist")
    }

    @discardableResult
    private static func shell(_ command: String) -> (out: String, code: Int32) {
        let task = Process()
        task.executableURL = URL(fileURLWithPath: "/bin/bash")
        task.arguments = ["-c", command]
        let pipe = Pipe()
        task.standardOutput = pipe
        task.standardError = pipe
        do {
            try task.run()
        } catch {
            return ("", -1)
        }
        task.waitUntilExit()
        let data = pipe.fileHandleForReading.readDataToEndOfFile()
        return (String(data: data, encoding: .utf8) ?? "", task.terminationStatus)
    }

    // MARK: - Monitor menubar app

    static var monitorAtLogin: Bool {
        FileManager.default.fileExists(atPath: monitorPlist.path)
    }

    /// Writes (or removes) the Monitor LaunchAgent and bootstraps/bootouts it.
    /// Points at wherever this bundle currently lives.
    static func setMonitorAtLogin(_ enabled: Bool) {
        if enabled {
            let bundlePath = Bundle.main.bundlePath
            let plist = """
                <?xml version="1.0" encoding="UTF-8"?>
                <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
                <plist version="1.0">
                <dict>
                    <key>Label</key>
                    <string>\(monitorLabel)</string>
                    <key>ProgramArguments</key>
                    <array>
                        <string>/usr/bin/open</string>
                        <string>-a</string>
                        <string>\(bundlePath)</string>
                    </array>
                    <key>RunAtLoad</key>
                    <true/>
                </dict>
                </plist>
                """
            try? plist.write(to: monitorPlist, atomically: true, encoding: .utf8)
            _ = shell("launchctl bootstrap \(gui) \(monitorPlist.path.replacingOccurrences(of: " ", with: "\\ ")) 2>/dev/null")
        } else {
            _ = shell("launchctl bootout \(gui)/\(monitorLabel) 2>/dev/null")
            try? FileManager.default.removeItem(at: monitorPlist)
        }
    }

    // MARK: - Whole collector

    /// True unless launchd overrides say disabled. Absence from the
    /// print-disabled list means enabled (installed runatload + keepalive).
    static var collectorAtLogin: Bool {
        let (out, _) = shell("launchctl print-disabled \(gui) 2>/dev/null")
        for line in out.components(separatedBy: "\n") where line.contains(collectorLabel) {
            return !line.contains("true")
        }
        return true
    }

    static func setCollectorAtLogin(_ enabled: Bool) {
        if enabled {
            _ = shell("launchctl enable \(gui)/\(collectorLabel)")
        } else {
            _ = shell("launchctl disable \(gui)/\(collectorLabel)")
        }
    }
}
