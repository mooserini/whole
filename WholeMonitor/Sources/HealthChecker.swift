import Foundation
import Combine

class HealthChecker: ObservableObject {
    @Published var combined: CombinedHealth?

    private var cancellables = Set<AnyCancellable>()
    private let baseURL = "http://127.0.0.1:39400"
    private let interval: TimeInterval
    private let quietAfterMinutes = 5.0
    private let iso = ISO8601DateFormatter()

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
        async let health: WholeHealth? = fetch(endpoint: "/health")
        async let status: WholeStatus? = fetch(endpoint: "/api/status")
        let (h, s) = await (health, status)

        let now = Date()
        let state: HealthState
        var error: String? = nil

        if h == nil && s == nil {
            state = .down
            error = "Cannot connect to Whole at \(baseURL)"
        } else {
            let running = h?.launchd?.running
                ?? h?.process?.alive
                ?? s?.collector?.processAlive
            if running == false {
                state = .down
                error = "Whole collector is not running"
            } else if let minutes = minutesSinceObservation(health: h, status: s, now: now),
                      minutes > quietAfterMinutes {
                // Running but quiet: change-only collector, nothing new to
                // record. Working as designed — nothing for Tom to do.
                state = .watching
            } else if running == true {
                state = .healthy
            } else {
                state = .unknown
            }
        }

        let result = CombinedHealth(state: state, health: h, status: s, lastCheck: now, error: error)
        await MainActor.run {
            self.combined = result
        }
    }

    private func minutesSinceObservation(health: WholeHealth?, status: WholeStatus?, now: Date) -> Double? {
        let stamp = status?.lastObservedAt ?? health?.lastObservedAt
        if let stamp, let date = iso.date(from: stamp) {
            return now.timeIntervalSince(date) / 60
        }
        if let age = status?.collector?.trailAgeSeconds ?? health?.trail?.ageSeconds {
            return age / 60
        }
        return nil
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
