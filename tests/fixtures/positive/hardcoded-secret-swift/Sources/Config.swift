import Foundation

enum APIConfig {
    static let stripeSecretKey = "sk_live_FixtureValueNotReal0123456789abcdef"
}

func saveSession(_ token: String) {
    UserDefaults.standard.set(token, forKey: "authToken")
}
