---
id: CORS-MISCONFIG
severity_max: HIGH
applies_to: swift
---

# Transport Trust Misconfig — ATS & Cert Validation (Swift)

## Intent

App iOS/macOS không có CORS, nhưng có đúng họ lỗi "nới lỏng trust policy cho chạy được việc": **App Transport Security (ATS)** và **server trust evaluation**. Rule này map CORS-MISCONFIG sang hai pattern Swift:

1. **ATS tắt** — `NSAllowsArbitraryLoads = true` trong `Info.plist`. Vibe coder gặp lỗi `App Transport Security has blocked a cleartext HTTP` (thường do dev server localhost HTTP) thì paste nguyên fix StackOverflow tắt ATS **toàn app**, rồi ship luôn. Mọi request HTTP cleartext được phép → MITM trên WiFi public đọc/sửa traffic, inject script vào webview.

2. **Trust-all certificate** — `URLSessionDelegate` (hoặc `WKNavigationDelegate`) `didReceive challenge` trả `.useCredential` với server trust **vô điều kiện**, không qua `SecTrustEvaluateWithError`. Thường để "fix" lỗi self-signed cert lúc dev. TLS thành trang trí: attacker MITM với cert bất kỳ.

Cả hai đều là config 1 dòng, dễ grep, và gần như không bao giờ chính đáng trong release build.

## Khi nào HIGH

- `Info.plist`: `NSAppTransportSecurity` → `NSAllowsArbitraryLoads: true` ở build release (không gate theo configuration)
- Delegate trust-all không điều kiện:
  ```
  completionHandler(.useCredential, URLCredential(trust: challenge.protectionSpace.serverTrust!))
  ```
  không có `SecTrustEvaluateWithError`/`SecTrustEvaluate` trước đó
- `NSExceptionAllowsInsecureHTTPLoads: true` cho domain nhận **credential/token** (login endpoint HTTP)
- App truyền dữ liệu nhạy cảm (auth, health, payment) — cộng hưởng với 2 pattern trên

## Khi nào MEDIUM / không flag (giảm cấp)

- `NSExceptionAllowsInsecureHTTPLoads` **scoped cho 1 domain** không nhạy cảm (tile map server, media CDN legacy) → MEDIUM, note migrate
- `NSAllowsArbitraryLoadsInWebContent: true` — chỉ nới cho webview, network API vẫn ATS → MEDIUM
- `NSAllowsLocalNetworking: true` — cho thiết bị LAN (IoT, printer), chấp nhận được → không flag
- Trust-all **gated đúng** trong `#if DEBUG` và chỉ cho host dev → note INFO (vẫn nhắc vì hay bị copy ra ngoài)

## Cách reasoning (KHÔNG pattern-match thuần)

1. **Grep/Read** mọi `Info.plist` (app + extension targets): key `NSAppTransportSecurity` và cây con.
2. **Grep** delegate: `didReceive challenge`, `serverTrust`, `URLCredential(trust:`.
3. **Verify điều kiện**: trust-all có nằm trong `#if DEBUG`? Có check host trước khi nới? Có gọi `SecTrustEvaluateWithError` không?
4. **Đánh giá data**: app gửi gì qua connection được nới? Token/PII → giữ HIGH; ảnh public → hạ MEDIUM.
5. ATS exception theo domain: domain đó serve gì, có nhận credential không?

## Search patterns (Swift-specific)

```
# Info.plist (XML)
NSAllowsArbitraryLoads
NSAllowsArbitraryLoadsInWebContent
NSExceptionAllowsInsecureHTTPLoads
NSExceptionDomains

# Trust-all delegate
didReceive challenge
URLCredential\(trust:
serverTrust
\.useCredential
AFSecurityPolicy.*allowInvalidCertificates|validatesDomainName\s*=\s*false   # Alamofire cũ
ServerTrustManager|DisabledTrustEvaluator                                    # Alamofire 5

# URL http:// hardcode (đi cùng ATS exception)
URL\(string:\s*"http://
```

## Examples

### HIGH — flag

```xml
<!-- Info.plist — tắt ATS toàn app -->
<key>NSAppTransportSecurity</key>
<dict>
    <key>NSAllowsArbitraryLoads</key>
    <true/>                                   <!-- BAD: mọi HTTP cleartext được phép -->
</dict>
```

```swift
// Trust-all — "fix" self-signed cert, ship luôn vào release
extension APIClient: URLSessionDelegate {
    func urlSession(_ session: URLSession, didReceive challenge: URLAuthenticationChallenge,
                    completionHandler: @escaping (URLSession.AuthChallengeDisposition, URLCredential?) -> Void) {
        completionHandler(.useCredential,
                          URLCredential(trust: challenge.protectionSpace.serverTrust!))  // BAD
    }
}
```

```swift
// Alamofire 5 — tắt evaluation cho domain production
let manager = ServerTrustManager(evaluators: [
    "api.example.com": DisabledTrustEvaluator()   // BAD
])
```

### NOT critical — safe

```xml
<!-- Exception scoped 1 domain media legacy, không credential -->
<key>NSAppTransportSecurity</key>
<dict>
    <key>NSExceptionDomains</key>
    <dict>
        <key>tiles.legacy-maps.example</key>
        <dict>
            <key>NSExceptionAllowsInsecureHTTPLoads</key>
            <true/>    <!-- MEDIUM note: chỉ tile ảnh public, migrate dần -->
        </dict>
    </dict>
</dict>
```

```swift
// Evaluate đàng hoàng, chỉ thêm logic cho host dev trong DEBUG
func urlSession(_ session: URLSession, didReceive challenge: URLAuthenticationChallenge,
                completionHandler: @escaping (URLSession.AuthChallengeDisposition, URLCredential?) -> Void) {
    guard let trust = challenge.protectionSpace.serverTrust else {
        return completionHandler(.cancelAuthenticationChallenge, nil)
    }
    #if DEBUG
    if challenge.protectionSpace.host == "dev.local" {
        return completionHandler(.useCredential, URLCredential(trust: trust))
    }
    #endif
    var error: CFError?
    if SecTrustEvaluateWithError(trust, &error) {
        completionHandler(.useCredential, URLCredential(trust: trust))
    } else {
        completionHandler(.cancelAuthenticationChallenge, nil)
    }
}
```

## Fix recommendation

1. **Xóa `NSAllowsArbitraryLoads`** — fix gốc là cho endpoint lên HTTPS. Dev server localhost: dùng `NSAllowsLocalNetworking` hoặc exception domain riêng trong Debug configuration (xcconfig per-config Info.plist), đừng tắt toàn cục.
2. Bắt buộc giữ HTTP cho 1 domain legacy → **`NSExceptionDomains` scoped**, kèm comment lý do + kế hoạch bỏ.
3. **Xóa delegate trust-all**; cert self-signed dev → cài CA dev vào simulator/device hoặc gate `#if DEBUG` + check host như ví dụ safe.
4. App nhạy cảm (fintech, health) → cân nhắc **certificate pinning** (`SecTrustCopyCertificateChain` so pin, hoặc Alamofire `PinnedCertificatesTrustEvaluator`) — pin có kiểm soát, kèm kế hoạch rotate.
5. Audit cả **extension targets** (share, widget, notification service) — mỗi target một `Info.plist` riêng, hay bị quên.

## Cross-references

- Rule `01-hardcoded-secret`: token gửi qua HTTP cleartext = lộ ngay trên đường truyền
- Rule `03-xss`: MITM inject script vào webview HTTP — ATS tắt là điều kiện cần
- Rule `09-ssrf`: scheme check `https` ở rule 09 vô nghĩa nếu ATS cho phép downgrade
