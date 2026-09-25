import SwiftUI
import Combine

struct MonitorView: View {
    @ObservedObject var healthChecker: HealthChecker
    weak var manager: StatusBarManager?

    private let tick = Timer.publish(every: 15, on: .main, in: .common).autoconnect()
    @State private var now = Date()
    @State private var showMore = false
    @State private var monitorLogin = false
    @State private var collectorLogin = true
    private static let iso = ISO8601DateFormatter()

    var body: some View {
        VStack(spacing: 0) {
            header
            Divider()
            statsGrid
            Divider()
            actions
            Divider()
            moreSection
            Spacer(minLength: 8)
        }
        .frame(width: 320)
        // Transparent root: the VibrantHostingController behind this view
        // supplies the frosted .popover glass. No solid fill anywhere.
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

                // When, not what: the last time the collector recorded
                // anything. Ticks live every 15s so yellow answers at a glance.
                Text("Last event · \(lastEventAgo)")
                    .font(.system(size: 10))
                    .foregroundColor(.secondary)
                    .onReceive(tick) { now = $0 }
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
                    value: formattedCount(healthChecker.combined?.status?.events),
                    icon: "doc.on.doc"
                )
                statCard(
                    label: "Active Time",
                    value: formattedActiveTime(healthChecker.combined?.status?.activeSecondsLowerBound),
                    icon: "clock"
                )
            }

            HStack(spacing: 10) {
                statCard(
                    label: "Privacy Clean",
                    value: formattedCount(healthChecker.combined?.status?.redactedEvents),
                    icon: "checkmark.shield"
                )
                statCard(
                    label: "Flagged",
                    value: formattedCount(healthChecker.combined?.status?.residualSensitiveFields),
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
                    restartCollectorScript()
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

    /// Guardian house pattern: More -> App Behavior, with the two login switches.
    private var moreSection: some View {
        VStack(spacing: 0) {
            // House pattern, same as Config Guardian: More -> App Behavior.
            Button {
            showMore.toggle()
            if showMore { refreshLoginState() }
        } label: {
            HStack(spacing: 6) {
                Image(systemName: "ellipsis.circle")
                    .font(.system(size: 12))
                Text("More")
                    .font(.system(size: 12, weight: .medium))
                Image(systemName: showMore ? "chevron.up" : "chevron.down")
                    .font(.system(size: 10, weight: .semibold))
            }
            .foregroundColor(.secondary)
            .frame(maxWidth: .infinity)
            .padding(.vertical, 6)
        }
        .buttonStyle(.plain)
        .padding(.horizontal, 12)

        if showMore {
            VStack(alignment: .leading, spacing: 2) {
                Text("APP BEHAVIOR")
                    .font(.system(size: 10, weight: .semibold))
                    .foregroundColor(.secondary)
                    .padding(.horizontal, 12)
                    .padding(.top, 4)

                Toggle("Launch Monitor at Login", isOn: $monitorLogin)
                    .font(.system(size: 12))
                    .toggleStyle(.switch)
                    .padding(.horizontal, 12)
                    .padding(.vertical, 4)
                    .onChange(of: monitorLogin) { _, value in
                        LoginItems.setMonitorAtLogin(value)
                        refreshLoginState()
                    }

                Toggle("Whole Collector at Login", isOn: $collectorLogin)
                    .font(.system(size: 12))
                    .toggleStyle(.switch)
                    .padding(.horizontal, 12)
                    .padding(.vertical, 4)
                    .onChange(of: collectorLogin) { _, value in
                        LoginItems.setCollectorAtLogin(value)
                        refreshLoginState()
                    }
            }
            .padding(.bottom, 6)
        }
        }
    }

    private func refreshLoginState() {
        monitorLogin = LoginItems.monitorAtLogin
        collectorLogin = LoginItems.collectorAtLogin
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
        .background(.thinMaterial, in: RoundedRectangle(cornerRadius: 8))
    }

    private var colorForState: Color {
        guard let hex = healthChecker.combined?.state.colorHex else { return .gray }
        if let nsColor = NSColor(hex: hex) {
            return Color(nsColor)
        }
        return .gray
    }

    /// "9m ago" for the last recorded event, or "--" when unknown.
    /// `now` ticks every 15s so the line stays live while the popover sits open.
    private var lastEventAgo: String {
        let _ = now
        guard let stamp = healthChecker.combined?.status?.lastObservedAt
                ?? healthChecker.combined?.health?.lastObservedAt,
              let date = Self.iso.date(from: stamp) else {
            return "--"
        }
        return timeAgo(date)
    }

    private func formattedCount(_ count: Int?) -> String {
        guard let count = count else { return "--" }
        let formatter = NumberFormatter()
        formatter.numberStyle = .decimal
        return formatter.string(from: NSNumber(value: count)) ?? String(count)
    }

    private func formattedActiveTime(_ seconds: Double?) -> String {
        guard let seconds = seconds else { return "--" }
        let hours = Int(seconds) / 3600
        let minutes = (Int(seconds) % 3600) / 60
        return "\(hours)h \(minutes)m"
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
