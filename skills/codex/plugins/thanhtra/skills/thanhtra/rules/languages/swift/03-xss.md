---
id: XSS
severity_max: HIGH
applies_to: swift
---

# XSS / Script Injection trong WKWebView (Swift)

## Intent

App Swift không có DOM, nhưng XSS sống lại nguyên vẹn khi app nhúng **WKWebView**. Ba cửa:

1. **`loadHTMLString`** — vibe coder dựng HTML bằng string interpolation từ content động (bio user, comment, message, JSON server) rồi load. Script attacker chạy trong webview của app.
2. **`evaluateJavaScript`** — ghép input vào chuỗi JS (`"showUser('\(name)')"`); input chứa `');...//` là thành code.
3. **JS bridge (`WKScriptMessageHandler`)** — native expose handler cho JS gọi (`window.webkit.messageHandlers.x.postMessage`). Nếu webview từng load content/URL không kiểm soát, script lạ gọi được bridge → đọc token, trigger hành vi native.

Impact khác browser: script trong webview đọc được cookie/localStorage của webview đó (thường chứa session khi app dùng web-login), gọi được bridge native, và phish trong UI app — user tin tuyệt đối vì "đây là app".

## Khi nào HIGH

- `loadHTMLString` với HTML ghép từ content L1 (data server trả về do user khác tạo: comment, bio, message, mô tả sản phẩm) **không escape**
- `evaluateJavaScript` ghép trực tiếp string L1 vào code JS
- `WKScriptMessageHandler` xử lý action nhạy cảm (trả token, mở URL, ghi file) **không check** `message.frameInfo.securityOrigin` / URL hiện tại, trong webview load content ngoài kiểm soát

## Khi nào MEDIUM (giảm cấp)

- HTML ghép từ content do chính user đó nhập, webview không có bridge + không có session → self-XSS
- `evaluateJavaScript` với giá trị đã encode qua `JSONEncoder`/`JSONSerialization`
- Webview chỉ load HTML tĩnh trong bundle, content động đã escape

## Cách reasoning (KHÔNG pattern-match thuần)

1. **Grep** sink: `loadHTMLString`, `evaluateJavaScript`, `callAsyncJavaScript`, `add(_:name:)` (script message handler), `loadFileURL`.
2. **Read** chỗ dựng HTML/JS string: có interpolation `\(...)` từ biến không phải constant?
3. **Trace** biến về nguồn: JSON server (content user khác = L1), deep link, hay literal trong bundle (L4)?
4. **Với bridge**: liệt kê action handler làm được; xem webview load gì (URL cố định của mình vs URL/HTML động); check có verify origin không.
5. **Verify escape**: có hàm escape HTML entity trước khi nhúng? JS arg có đi qua JSON encode?

## Search patterns (Swift-specific)

```
# HTML động
loadHTMLString\("[^"]*\\\(
loadHTMLString\([a-zA-Z_]    # biến HTML dựng sẵn — read ngược chỗ dựng

# JS ghép string
evaluateJavaScript\("[^"]*\\\(
evaluateJavaScript\([a-zA-Z_]\w*\s*[,)]   # biến — read ngược

# Bridge
userContentController[\s\S]{0,200}didReceive
\.add\(self,\s*name:
javaScriptEnabled|allowsContentJavaScript
```

## Examples

### HIGH — flag

```swift
// Render comment của user khác bằng interpolation — script chạy thẳng
func showComment(_ comment: Comment) {
    let html = """
        <html><body>
        <div class="author">\(comment.authorName)</div>
        <div class="body">\(comment.body)</div>            <!-- BAD: L1 không escape -->
        </body></html>
        """
    webView.loadHTMLString(html, baseURL: nil)
}
```

```swift
// Ghép tên user vào JS — name = "');stealToken();//" là xong
webView.evaluateJavaScript("setGreeting('\(user.displayName)')")   // BAD
```

```swift
// Bridge trả token cho mọi frame — webview này load cả URL từ deep link
func userContentController(_ ucc: WKUserContentController, didReceive message: WKScriptMessage) {
    if message.name == "getToken" {
        webView.evaluateJavaScript("onToken('\(session.token)')")   // BAD: không check origin
    }
}
```

### NOT critical — safe

```swift
// Escape HTML entity trước khi nhúng
func htmlEscape(_ s: String) -> String {
    s.replacingOccurrences(of: "&", with: "&amp;")
     .replacingOccurrences(of: "<", with: "&lt;")
     .replacingOccurrences(of: ">", with: "&gt;")
     .replacingOccurrences(of: "\"", with: "&quot;")
}
let html = "<div>\(htmlEscape(comment.body))</div>"
```

```swift
// Truyền data vào JS qua JSON encode — không ghép code
let payload = try JSONEncoder().encode(user)
let json = String(data: payload, encoding: .utf8)!
webView.callAsyncJavaScript("render(user)", arguments: ["user": json], in: nil,
                            contentWorld: .page)

// Hoặc: evaluateJavaScript("render(\(json))") — json đã là JSON literal hợp lệ
```

```swift
// Bridge check origin trước khi làm action nhạy cảm
guard let origin = message.frameInfo.securityOrigin as WKSecurityOrigin?,
      origin.host == "app.example.com", origin.protocol == "https" else { return }
```

## Fix recommendation

1. **Escape HTML entity** cho mọi content động trước khi vào `loadHTMLString`; tốt hơn nữa: render bằng native view (SwiftUI/`UITextView` + AttributedString), chỉ dùng webview khi thật cần.
2. **Không ghép string vào JS** — `callAsyncJavaScript` với `arguments:` dict, hoặc encode qua `JSONEncoder` rồi nhúng như JSON literal.
3. **Bridge**: check `message.frameInfo.securityOrigin` host + scheme; tách webview "content lạ" (không bridge, không cookie) khỏi webview "app UI" (có bridge, chỉ load origin mình).
4. Webview hiển thị content thuần → `config.defaultWebpagePreferences.allowsContentJavaScript = false`.
5. Set `baseURL: nil` khi load HTML động để script (nếu lọt) không có origin mà gọi API.

## Cross-references

- Rule `09-ssrf`: deep link điều khiển URL webview — script lạ + bridge = combo chiếm session
- Rule `01-hardcoded-secret`: token trong webview cookie/localStorage là mục tiêu của script injected
- Rule `15-cors-misconfig`: ATS tắt → webview load HTTP, MITM inject script sạch sẽ
