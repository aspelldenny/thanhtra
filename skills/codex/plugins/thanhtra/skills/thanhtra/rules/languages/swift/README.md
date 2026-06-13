# Swift Specialization

These rule files override generic rules when Thanh Tra detects the primary language as Swift (iOS/macOS apps, plus Vapor server-side).

## How override works

When Thanh Tra scans a repo and detects primary language `swift`, for each rule id present in BOTH `rules/generic/<id>.md` AND `rules/languages/swift/<id>.md`, the language-specific version REPLACES the generic. Generic rules without a Swift override apply as-is.

Override matching is by frontmatter `id`, not filename — convention is to keep the same numeric prefix as the generic counterpart.

## Files in this folder

| File | Rule ID | What it specializes |
|---|---|---|
| `01-hardcoded-secret.md` | HARDCODED-SECRET | Key trong Swift literal / `Info.plist` / `.xcconfig` (binary strings được hết), token vào `UserDefaults` thay vì Keychain, nuance Firebase/publishable key không phải secret |
| `02-sql-injection.md` | SQL-INJECTION | GRDB `execute(sql:)` interpolation (bad) vs `execute(literal:)`/`arguments:` (safe), FMDB, sqlite3 C API, `NSPredicate(format:)` injection, severity theo nguồn L1 mobile |
| `03-xss.md` | XSS | WKWebView `loadHTMLString` HTML động, `evaluateJavaScript` ghép string, JS bridge (`WKScriptMessageHandler`) không check origin |
| `08-insecure-deserialization.md` | INSECURE-DESERIALIZATION | `NSKeyedUnarchiver.unarchiveObject` deprecated, `requiresSecureCoding = false`, allowlist `NSObject.self` vô nghĩa, Codable là đường safe |
| `09-ssrf.md` | SSRF | Arbitrary URL load: deep link / universal link / push payload → WKWebView/`URLSession`, token tự gắn bay sang host attacker, allowlist host equality (không `contains`), Vapor server = SSRF cổ điển |
| `15-cors-misconfig.md` | CORS-MISCONFIG | Map sang transport trust: ATS `NSAllowsArbitraryLoads`, trust-all `URLSessionDelegate`, Alamofire `DisabledTrustEvaluator`, exception scoped vs toàn cục |

**Note on rule-id mapping:** app Swift không có CORS/SSRF theo nghĩa web — rule 15 map sang ATS + cert-validation bypass (cùng họ "nới lỏng origin/transport trust"), rule 09 map sang arbitrary URL load (cùng họ "attacker điều khiển URL mà code tin"). Giữ id canonical để report so sánh được cross-language.

## L1 trên mobile khác web

Nguồn untrusted (L1) đặc trưng app: deep link / custom URL scheme (app nào trên máy cũng gọi được), universal link, push notification payload, pasteboard, file import / AirDrop / share extension, QR/NFC scan, và content server trả về do **user khác** tạo. TextField của chính user vẫn là L1 nhưng impact thường tự hại mình — các rule ghi rõ cách giảm cấp.

## Reasoning still applies

Language overrides do NOT skip the L1–L4 data flow analysis. They give MORE PRECISE patterns for Swift idioms (SwiftUI/UIKit entry points, WKWebView, URLSession, GRDB, Core Data, Keychain), but the LLM agent must still:

1. **Grep** với pattern Swift-specific
2. **Read** đầy đủ handler/coordinator chứa sink
3. **Trace** L1 (deep link/push/server content) → L2 → L3 (plist/xcconfig) → L4 (constant)
4. **Verify** sanitization context (bind `?`/`literal:`, `%@` placeholder, host allowlist equality, `ofClasses:` hẹp, HTML escape)

## Frameworks / APIs covered

- SwiftUI `onOpenURL`, UIKit `AppDelegate`/`SceneDelegate` (entry points)
- WKWebView, SFSafariViewController (web content)
- URLSession, Alamofire (HTTP + trust evaluation)
- GRDB, FMDB, SQLite.swift, sqlite3 C API, Core Data / NSPredicate (storage)
- NSKeyedUnarchiver / NSSecureCoding, Codable (serialization)
- Keychain Services, UserDefaults (secret storage)
- App Transport Security / Info.plist (transport policy)
- Vapor (server-side Swift — SSRF/SQLi cổ điển)

## Contributing

To add a new Swift-specific override:

1. Pick a rule id from `rules/generic/`
2. Copy the generic file's frontmatter, change `applies_to: swift`
3. Replace search patterns + examples with Swift idiom
4. Keep the Intent + L1–L4 reasoning approach
5. Test by running `/thanhtra` on a Swift repo with that vulnerability
