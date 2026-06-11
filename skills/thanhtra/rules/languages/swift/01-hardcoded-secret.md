---
id: HARDCODED-SECRET
severity_max: CRITICAL
applies_to: swift
---

# Hardcoded Secret (Swift)

## Intent

App iOS/macOS bị dịch ngược cực dễ: `strings MyApp.app/MyApp`, `plutil -p Info.plist`, hoặc tải `.ipa` về unzip là đọc được mọi literal trong binary và mọi value trong plist. Vibe coder hay nhét thẳng API key vào code Swift, `Info.plist`, hoặc `.xcconfig` rồi commit — và hay lưu token đăng nhập vào `UserDefaults` (plaintext, nằm trong backup) thay vì Keychain.

Hai họ lỗi gộp trong rule này:

1. **Secret nhúng trong bundle** — key vendor (OpenAI, Stripe, AWS...) nằm trong code/plist/xcconfig. Bất kỳ ai cài app đều extract được.
2. **Secret lưu sai chỗ lúc runtime** — token/password ghi vào `UserDefaults`/file plaintext thay vì Keychain.

## Khi nào CRITICAL / HIGH

**CRITICAL:**
- Key dạng **server-class** trong code/plist/xcconfig committed: Stripe `sk_live_`, OpenAI `sk-`, Anthropic `sk-ant-`, AWS `AKIA...` + secret, DB connection string, private key PEM. Ai extract được là gọi API/charge tiền/đọc DB dưới danh nghĩa chủ app.
- `.xcconfig` hoặc `Secrets.plist` chứa key thật và **không có trong `.gitignore`**.

**HIGH (giảm cấp):**
- Token user (JWT, OAuth access/refresh token) lưu `UserDefaults` — lộ khi backup không mã hóa, jailbreak, hoặc malware đọc sandbox; nhưng chỉ ảnh hưởng user đó.
- API key vendor loại "client key" có quota/billing (Google Maps, weather API trả phí) — bị abuse quota chứ không leak data.

**KHÔNG flag (false positive phổ biến):**
- `GoogleService-Info.plist` / Firebase `API_KEY` — Google thiết kế để nhúng client, không phải secret (bảo vệ bằng Firebase Rules). Chỉ note INFO nếu thiếu App Check.
- Public key pinning data, publishable key Stripe (`pk_live_`), DSN Sentry — by design là public.

## Cách reasoning (KHÔNG pattern-match thuần)

1. **Grep** literal trong `.swift`, value trong `*.plist`, `*.xcconfig`, `*.entitlements`.
2. **Phân loại key**: prefix nói lên loại — `sk_live_`/`sk-`/`AKIA` là server-class; `pk_`/Firebase là client-class.
3. **Trace nơi dùng**: key gọi thẳng API vendor từ app (`URLRequest` + `Authorization: Bearer \(key)`) → đúng là secret nhúng client. Key chỉ dùng làm identifier → hạ cấp.
4. **Với storage**: grep `UserDefaults` xem value được set là gì — token/password → flag; setting UI thường (theme, locale) → bỏ qua.

## Search patterns (Swift-specific)

```
# Literal trong Swift code
let\s+\w*(key|token|secret|password|credential)\w*\s*=\s*"
(apiKey|api_key|secretKey|accessToken|authToken)\s*[:=]\s*"
"(sk-ant-|sk-|sk_live_|AKIA|ghp_|xox[bp]-)
Authorization.*Bearer \\?\(

# Plist / xcconfig
plutil -p **/*.plist | grep -i "key\|secret\|token"
(API_KEY|SECRET|TOKEN|PASSWORD)\s*=     # trong *.xcconfig

# UserDefaults lưu credential
UserDefaults\.(standard|init)[\s\S]{0,80}set\([^)]*(token|password|secret|credential|jwt)
@AppStorage\("[^"]*(token|password|secret)
```

## Examples

### CRITICAL — flag

```swift
// Key OpenAI nhúng thẳng — strings binary là ra
enum API {
    static let openAIKey = "sk-proj-AbCd1234..."   // BAD: server-class key trong bundle
}

var req = URLRequest(url: URL(string: "https://api.openai.com/v1/chat/completions")!)
req.setValue("Bearer \(API.openAIKey)", forHTTPHeaderField: "Authorization")
```

```
// Secrets.xcconfig — committed vào repo
STRIPE_SECRET_KEY = sk_live_51Hxxxxx   // BAD: sk_live là key server-side
```

### HIGH — flag

```swift
// Token đăng nhập vào UserDefaults — plaintext trong sandbox + backup
func saveSession(_ token: String) {
    UserDefaults.standard.set(token, forKey: "authToken")   // BAD: dùng Keychain
}
```

### NOT critical — safe

```swift
// Token vào Keychain
let query: [String: Any] = [
    kSecClass as String: kSecClassGenericPassword,
    kSecAttrAccount as String: "authToken",
    kSecValueData as String: token.data(using: .utf8)!,
    kSecAttrAccessible as String: kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly,
]
SecItemAdd(query as CFDictionary, nil)
```

```swift
// Stripe publishable key — by design public
StripeAPI.defaultPublishableKey = "pk_live_..."

// Firebase config — client-class, không flag
// GoogleService-Info.plist: API_KEY = AIzaSy...
```

## Fix recommendation

1. **Server-class key KHÔNG BAO GIỜ vào app bundle** — dựng backend proxy (hoặc serverless function) giữ key, app gọi proxy với auth của user.
2. **Token runtime → Keychain** (`SecItemAdd`/`SecItemCopyMatching` hoặc wrapper như KeychainAccess), set `kSecAttrAccessible` mức chặt nhất app chịu được.
3. **Key build-time** → `.xcconfig` gitignored + inject từ CI (fastlane match-style); đọc qua `Bundle.main.object(forInfoDictionaryKey:)` từ plist generated.
4. Key đã lộ trong git history → **revoke + rotate ngay**, không chỉ xóa file.
5. Firebase: bật **App Check** để client-key không bị abuse.

## Cross-references

- Rule `15-cors-misconfig`: ATS tắt + token plaintext = sniff được cả transport lẫn storage
- Rule `09-ssrf`: deep link điều khiển URL + Bearer token tự gắn = token gửi sang host attacker
- Rule `20-outdated-dependency`: SDK vendor cũ có thể log key ra console
