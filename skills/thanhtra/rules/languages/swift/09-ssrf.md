---
id: SSRF
severity_max: HIGH
applies_to: swift
---

# SSRF / Arbitrary URL Load (Swift)

## Intent

Trong app iOS/macOS, biến thể client của SSRF là **arbitrary URL load**: URL do attacker điều khiển đi vào `WKWebView.load` hoặc `URLSession` của app. Nguồn L1 đặc trưng mobile:

- **Deep link / custom scheme**: `myapp://open?url=https://...` — bất kỳ app/web nào trên máy cũng gọi được scheme của app
- **Universal link** query params
- **Push notification payload** (`userInfo["url"]`) — server bị compromise hoặc provider push thứ ba
- **QR code / NFC scan**

Impact: (1) webview có session cookie/JS bridge load trang attacker → phishing trong UI app + gọi bridge (xem rule 03); (2) code tự gắn `Authorization` header rồi fetch URL động → **token bay sang host attacker**; (3) scheme không lọc → `file://` đọc file sandbox vào webview, `javascript:` chạy script.

Swift chạy **server-side** (Vapor) thì là SSRF cổ điển: URL từ `req.query` vào `client.get(...)` → đọc metadata endpoint/internal service. Reasoning giống generic, sink là `req.client`/`URLSession` trên server.

## Khi nào HIGH

- URL từ deep link/universal link/push payload đi **không qua validate** vào:
  - `webView.load(URLRequest(url:))` — webview có cookie đăng nhập hoặc script message handler
  - `URLSession.dataTask`/`data(for:)` mà request **tự gắn token** (`Authorization`, API key header)
- Không check **scheme** → `file://`, `javascript:` lọt vào webview
- Vapor server: URL/host từ request vào `req.client.get`/`URLSession` không allowlist → check thêm private IP/metadata như generic rule

## Khi nào MEDIUM (giảm cấp)

- URL động chỉ mở bằng `UIApplication.shared.open` / `SFSafariViewController` (sandbox riêng, không cookie app, không bridge) — còn lại risk phishing nhẹ
- Có check host nhưng bằng `hasSuffix`/`contains` (bypass bằng `evil-example.com` / `example.com.evil.io`) → flag MEDIUM với note bypass
- URL từ server response của chính backend mình (L2) — chỉ note nếu backend cho user khác inject URL

## Cách reasoning (KHÔNG pattern-match thuần)

1. **Grep** entry point: `onOpenURL`, `application(_:open:options:)`, `application(_:continue:restorationHandler:)`, `scene(_:openURLContexts:)`, `didReceiveRemoteNotification`, `userNotificationCenter(_:didReceive:)`.
2. **Trace** URL/string từ entry → có vào `webView.load`, `URLSession`, `UIApplication.open` không (kể cả qua Router/Coordinator trung gian — read các lớp đó).
3. **Verify validate**: parse bằng `URLComponents` rồi so `host` **bằng `==`/allowlist Set** chưa? Check `scheme == "https"` chưa?
4. **Đánh giá đích**: webview đích có cookie session/bridge không? Request có gắn credential không? Quyết định HIGH vs MEDIUM.

## Search patterns (Swift-specific)

```
# Entry point deep link / push
onOpenURL\s*\{
func application\(_[^)]*open url
openURLContexts
didReceiveRemoteNotification|userNotificationCenter

# URL từ string động vào sink
webView\.load\(URLRequest\(url:
URL\(string:\s*[a-zA-Z_][^)]*\)   # URL từ biến — trace ngược
UIApplication\.shared\.open\(

# Token tự gắn + URL động
setValue\([^)]*Authorization[\s\S]{0,300}dataTask
addValue\("Bearer

# Host check yếu
host[\s\S]{0,40}(hasSuffix|contains)\(
```

## Examples

### HIGH — flag

```swift
// Deep link → thẳng vào webview có session
.onOpenURL { url in
    let comps = URLComponents(url: url, resolvingAgainstBaseURL: false)
    if let target = comps?.queryItems?.first(where: { $0.name == "url" })?.value,
       let dest = URL(string: target) {
        webView.load(URLRequest(url: dest))   // BAD: không check host/scheme
    }
}
```

```swift
// Push payload điều khiển URL, request tự gắn token
func userNotificationCenter(_ c: UNUserNotificationCenter, didReceive r: UNNotificationResponse,
                            withCompletionHandler done: @escaping () -> Void) {
    if let s = r.notification.request.content.userInfo["url"] as? String, let u = URL(string: s) {
        var req = URLRequest(url: u)
        req.setValue("Bearer \(session.token)", forHTTPHeaderField: "Authorization")  // BAD
        URLSession.shared.dataTask(with: req).resume()    // token gửi tới host bất kỳ
    }
    done()
}
```

```swift
// Host check bằng contains — bypass: https://evil.com/?x=example.com
guard urlString.contains("example.com") else { return }   // BAD (MEDIUM)
webView.load(URLRequest(url: URL(string: urlString)!))
```

### NOT critical — safe

```swift
// Allowlist host tuyệt đối + scheme check
let allowedHosts: Set<String> = ["app.example.com", "help.example.com"]
guard let comps = URLComponents(url: url, resolvingAgainstBaseURL: false),
      comps.scheme == "https",
      let host = comps.host, allowedHosts.contains(host) else { return }
webView.load(URLRequest(url: comps.url!))
```

```swift
// URL lạ → mở bằng Safari VC (sandbox riêng, không cookie app, không bridge)
present(SFSafariViewController(url: externalURL), animated: true)
```

```swift
// Deep link chỉ mang ID, URL dựng từ constant
if let id = comps?.queryItems?.first(where: { $0.name == "productID" })?.value {
    let url = URL(string: "https://api.example.com/products/\(id)")!  // host cố định
}
```

## Fix recommendation

1. **Deep link mang ID, không mang URL** — `myapp://product?id=123` rồi tự dựng URL từ host constant; tránh được cả lớp lỗi.
2. Bắt buộc nhận URL → parse `URLComponents`, check `scheme == "https"` và `host` so **bằng equality với allowlist Set** (không `hasSuffix`/`contains`).
3. URL ngoài allowlist → `SFSafariViewController`/`UIApplication.open`, **không bao giờ** vào webview có session/bridge.
4. Token chỉ gắn khi `host` thuộc allowlist API của mình — viết một `AuthorizedClient` duy nhất làm việc này, đừng rải `setValue("Bearer ...)` khắp nơi.
5. Vapor server: thêm chặn private/metadata IP (127.0.0.0/8, 10/8, 172.16/12, 192.168/16, 169.254.169.254) sau khi resolve — như generic rule.

## Cross-references

- Rule `03-xss`: URL lạ vào webview có bridge = script gọi bridge — combo của rule này
- Rule `01-hardcoded-secret`: token gắn header là thứ bị đánh cắp khi URL động
- Rule `15-cors-misconfig`: ATS tắt thì URL http:// cũng lọt, thêm MITM vào chuỗi
