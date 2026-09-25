import Foundation

// Standalone contract proof: decodes Models.swift against the LIVE Whole
// server. Exit 0 = the menu-bar app will read real state, not red forever.
// Compile: swiftc Sources/Models.swift Tools/contract-test.swift -o /tmp/t && /tmp/t

struct ContractError: Error, CustomStringConvertible {
    let message: String
    var description: String { message }
}

func fetch<T: Decodable>(_ type: T.Type, endpoint: String) throws -> T {
    guard let url = URL(string: "http://127.0.0.1:39400" + endpoint) else {
        throw ContractError(message: "bad url: \(endpoint)")
    }
    var request = URLRequest(url: url)
    request.timeoutInterval = 10
    var result: Result<T, Error>?
    let sema = DispatchSemaphore(value: 0)
    URLSession.shared.dataTask(with: request) { data, response, error in
        defer { sema.signal() }
        do {
            if let error { throw error }
            guard let http = response as? HTTPURLResponse, http.statusCode == 200 else {
                throw ContractError(message: "\(endpoint): non-200")
            }
            result = .success(try JSONDecoder().decode(T.self, from: data ?? Data()))
        } catch {
            result = .failure(error)
        }
    }.resume()
    sema.wait()
    return try result!.get()
}

@main
struct ContractTest {
    static func main() {
        do {
            let health = try fetch(WholeHealth.self, endpoint: "/health")
            let status = try fetch(WholeStatus.self, endpoint: "/api/status")
            print("health: overall=\(health.overall ?? "?") launchd.running=\(health.launchd?.running.map(String.init(describing:)) ?? "?") process.alive=\(health.process?.alive.map(String.init(describing:)) ?? "?") trail.fresh=\(health.trail?.fresh.map(String.init(describing:)) ?? "?") last=\(health.lastObservedAt ?? "?")")
            print("status: events=\(status.events.map(String.init(describing:)) ?? "?") redacted=\(status.redactedEvents.map(String.init(describing:)) ?? "?") residual=\(status.residualSensitiveFields.map(String.init(describing:)) ?? "?") active_s=\(status.activeSecondsLowerBound.map(String.init(describing:)) ?? "?") collector=\(status.collector?.state ?? "?")/alive=\(status.collector?.processAlive.map(String.init(describing:)) ?? "?")")
            guard health.launchd?.running != nil || health.process?.alive != nil else {
                throw ContractError(message: "no running signal decoded — models out of contract")
            }
            guard status.events != nil else {
                throw ContractError(message: "no event count decoded — models out of contract")
            }
            print("CONTRACT OK")
        } catch {
            print("CONTRACT FAIL: \(error)")
            exit(1)
        }
    }
}
