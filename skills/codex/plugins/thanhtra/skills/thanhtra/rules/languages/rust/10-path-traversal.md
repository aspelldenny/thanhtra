---
id: PATH-TRAVERSAL
severity_max: HIGH
applies_to: rust
---

# Path Traversal (Rust)

## Intent

App Rust đọc/ghi file theo tên do **L1 input** cung cấp: `fs::read(format!("uploads/{}", name))`, `File::open(path)`, `tokio::fs::read`. Nếu không sanitize, attacker gửi `../../etc/passwd` hoặc absolute path `/etc/shadow` để thoát thư mục cho phép. `PathBuf::push` với absolute path còn **thay thế** toàn bộ base — bẫy đặc trưng Rust.

## Khi nào HIGH

- L1 input ghép vào path đọc/ghi: `fs::read`, `fs::read_to_string`, `File::open`, `fs::write`, `tokio::fs::*`
- `base.join(user_input)` hoặc `base.push(user_input)` mà user_input có thể là `../...` hoặc absolute
- Serve file tĩnh theo param: axum handler dựng path từ `Path(name)`, hoặc cấu hình `ServeDir` sai

## Khi nào MEDIUM (giảm cấp)

- Có check `contains("..")` nhưng quên absolute path, symlink, hoặc encoding (`%2e%2e`)
- Chỉ ghép tên file vào extension cố định nhưng vẫn cho `/` trong tên

## Cách reasoning (KHÔNG pattern-match thuần)

1. **Grep** sink: `fs::read`, `fs::write`, `File::open`, `File::create`, `tokio::fs`, `.join(`, `.push(`, `ServeDir`.
2. **Read**: tên file trace về extractor (`Path(name)`, `Query`, multipart filename) không?
3. **Bẫy `PathBuf`**:
   - `base.join("/etc/passwd")` → kết quả là `/etc/passwd` (absolute thắng base). NGUY HIỂM.
   - `base.join("../../x")` → thoát base. NGUY HIỂM.
4. **Verify**: có canonicalize + check `starts_with(base)` không? Có chỉ lấy `file_name()` không?

## Search patterns (Rust-specific)

```
fs::(read|read_to_string|write|File::open|File::create)\s*\(\s*&?format!
tokio::fs::(read|write|File)
\.join\s*\(\s*&?[a-z_]*(name|path|file|input)
\.push\s*\(\s*&?[a-z_]*(name|path|file|input)
ServeDir::new
```

## Examples

### HIGH — flag

```rust
// axum — tên file từ path param ghép thẳng
async fn download(Path(name): Path<String>) -> impl IntoResponse {
    let data = tokio::fs::read(format!("uploads/{}", name)).await.unwrap(); // ../../etc/passwd
    data
}
```

```rust
// PathBuf::join với input absolute thay thế base
let mut p = PathBuf::from("/srv/files");
p.push(&user_name); // user_name = "/etc/shadow" → p == "/etc/shadow"
let content = std::fs::read(p)?;
```

### NOT high — safe

```rust
// Chỉ lấy file_name (bỏ mọi thành phần thư mục), rồi canonicalize + check base
let base = std::fs::canonicalize("uploads")?;
let candidate = base.join(
    Path::new(&name).file_name().ok_or_else(bad_request)?  // bỏ ../ và path phân cấp
);
let full = std::fs::canonicalize(&candidate)?;
if !full.starts_with(&base) {
    return Err(forbidden());
}
let data = std::fs::read(full)?;
```

## Fix recommendation

1. **Lấy `Path::new(input).file_name()`** để vứt mọi thành phần thư mục và `..`.
2. **Canonicalize** base + path đích, rồi check `full.starts_with(base)`.
3. **Không bao giờ `join`/`push` raw input** — absolute path sẽ thay base.
4. **Serve file tĩnh**: dùng `tower_http::services::ServeDir` (đã chống traversal) thay vì tự dựng path.
5. **Validate** tên theo allowlist ký tự (`[A-Za-z0-9_.-]`), reject `/`, `\`, `..`, null byte.

## Cross-references

- Rule `16-unrestricted-file-upload`: upload + path traversal = ghi đè file hệ thống
- Rule `09-ssrf`: scheme `file://` trong URL fetch cũng đọc file nội bộ
