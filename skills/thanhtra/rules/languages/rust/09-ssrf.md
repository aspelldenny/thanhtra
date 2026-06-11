---
id: SSRF
severity_max: HIGH
applies_to: rust
---

# SSRF (Rust)

## Intent

App Rust fetch URL phía server bằng `reqwest`, `ureq`, `hyper`, `isahc`. Nếu URL (hoặc host/port/path) do **L1 input** điều khiển mà không validate, attacker ép server gọi `http://169.254.169.254/` (cloud metadata → credentials), `http://localhost:6379` (Redis/DB nội bộ), hoặc internal service không expose ra ngoài.

Rust không có "magic" chống SSRF — `reqwest::get(user_url)` đi thẳng.

## Khi nào HIGH

- L1 input (axum `Query`/`Json`, actix extractor) truyền thẳng/ghép vào `reqwest::get()`, `client.get(url)`, `ureq::get(&url)`
- "URL preview", "fetch image from URL", "webhook test", "import from URL" feature
- Proxy/relay endpoint nhận URL đích từ client

## Khi nào MEDIUM (giảm cấp)

- Có allowlist domain nhưng dùng `url.contains("trusted.com")` (bypass bằng `trusted.com.evil.com` hoặc `evil.com/?x=trusted.com`)
- Chỉ chặn `localhost`/`127.0.0.1` literal mà quên `0.0.0.0`, IPv6 `[::1]`, decimal IP, `169.254.169.254`, DNS rebinding

## Cách reasoning (KHÔNG pattern-match thuần)

1. **Grep** sink: `reqwest::get`, `.get(`, `.post(`, `Client::new()...send()`, `ureq::`, `hyper::`.
2. **Read** handler: URL có trace về request không? `format!("https://{}/...", user_host)` cũng là SSRF qua host.
3. **Kiểm validate**:
   - Parse bằng `url::Url::parse` rồi check `host_str()` theo **allowlist tuyệt đối** (== domain), không phải `contains`.
   - Có resolve IP và chặn private/link-local/loopback range không?
4. **Verify**: redirect có bị follow tới internal không (`reqwest` follow redirect mặc định)?

## Search patterns (Rust-specific)

```
reqwest::(get|Client)
\.get\s*\(\s*&?(format!|[a-z_]*url)
ureq::(get|post|request)
hyper::.*Uri::from
isahc::(get|Request)
Url::parse\s*\(\s*&?[a-z_]*(url|host|target)
```

## Examples

### HIGH — flag

```rust
// axum — URL từ query đi thẳng vào reqwest
async fn preview(Query(p): Query<UrlParam>) -> impl IntoResponse {
    let body = reqwest::get(&p.url).await.unwrap().text().await.unwrap(); // L1, no validate
    Html(body)
}
```

```rust
// host do user kiểm soát, ghép vào URL
let endpoint = format!("https://{}/api/data", user_host); // L1 host
let resp = client.get(&endpoint).send().await?;            // SSRF qua host
```

### NOT high — safer

```rust
// Allowlist tuyệt đối theo host đã parse
let parsed = Url::parse(&p.url).map_err(|_| bad_request())?;
let host = parsed.host_str().ok_or_else(bad_request)?;
const ALLOWED: &[&str] = &["api.partner.com", "cdn.partner.com"];
if !ALLOWED.contains(&host) {
    return Err(forbidden());
}
let body = reqwest::get(parsed).await?.text().await?;
```

## Fix recommendation

1. **Allowlist domain tuyệt đối** sau khi `Url::parse` — so sánh `host_str()` `==`, không `contains`.
2. **Chặn private/link-local IP**: resolve host, reject `10/8`, `172.16/12`, `192.168/16`, `127/8`, `169.254/16`, `::1`, `fc00::/7`. Có crate hỗ trợ (vd kiểm `IpAddr::is_loopback()/is_private()`).
3. **Tắt/giới hạn redirect**: `reqwest::Client::builder().redirect(Policy::none())` rồi tự validate từng hop.
4. **Timeout + giới hạn kích thước** response để giảm tác hại.
5. **Tách network egress**: chạy fetcher trong môi trường không reach được internal/metadata endpoint.

## Cross-references

- Rule `10-path-traversal`: `file://` scheme trong fetch → đọc file nội bộ
- Rule `17-verbose-error-debug-mode`: lỗi reqwest trả về client lộ internal host/IP
