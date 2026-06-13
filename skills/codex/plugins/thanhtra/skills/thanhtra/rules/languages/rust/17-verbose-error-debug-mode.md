---
id: VERBOSE-ERROR-DEBUG-MODE
severity_max: HIGH
applies_to: rust
---

# Verbose Error / Debug Mode (Rust)

## Intent

App Rust trả lỗi nội bộ thẳng cho client: `format!("{:?}", err)`, `err.to_string()`, hoặc cả chuỗi `anyhow`/`eyre` (kèm backtrace) vào HTTP body. Lộ SQL query + schema (sqlx error), đường dẫn file, internal host/IP, struct nội bộ. Vibe code hay `.map_err(|e| (StatusCode::INTERNAL_SERVER_ERROR, e.to_string()))` cho nhanh.

## Khi nào HIGH

- Handler trả `{:?}`/`{:#?}`/`.to_string()` của error ra response body
- `anyhow::Error`/`eyre::Report` đưa thẳng vào body (chain + backtrace lộ hết)
- `RUST_BACKTRACE=1`/`full` bật ở production (in backtrace vào log/response)
- Framework error handler mặc định in chi tiết (một số setup axum/actix trả `Debug` của error)

## Khi nào MEDIUM/LOW

- Chỉ log nội bộ (`tracing::error!`) còn response trả message generic → LOW
- Lộ message chung chung không có schema/path/secret → MEDIUM

## Cách reasoning (KHÔNG pattern-match thuần)

1. **Grep** sink: `e.to_string()`, `format!("{:?}"`, `{:#?}`, `IntoResponse` impl, `map_err`, `anyhow`, `eyre`.
2. **Read** error path: cái gì thực sự đi vào **response body** gửi cho client (khác với log)?
3. **Phân biệt**: log chi tiết (OK) vs trả chi tiết cho client (BAD).
4. **Verify**: response cho client có map về message generic + mã lỗi, còn chi tiết chỉ vào `tracing`/log?

## Search patterns (Rust-specific)

```
\.to_string\(\)\s*\)            # gần (StatusCode::..., e.to_string())
format!\s*\(\s*"\{:#?\}"|\{:\?\}"
map_err\s*\(\s*\|e\|.*to_string
anyhow::Error|eyre::Report      # đưa thẳng vào IntoResponse
RUST_BACKTRACE
```

## Examples

### HIGH — flag

```rust
// axum — to_string() của error sqlx ra body (lộ SQL + schema)
async fn handler(State(pool): State<PgPool>) -> Result<Json<T>, (StatusCode, String)> {
    let row = sqlx::query!("...").fetch_one(&pool).await
        .map_err(|e| (StatusCode::INTERNAL_SERVER_ERROR, e.to_string()))?; // BAD
    Ok(Json(/* ... */))
}
```

```rust
// anyhow chain + backtrace vào response
impl IntoResponse for AppError {
    fn into_response(self) -> Response {
        (StatusCode::INTERNAL_SERVER_ERROR, format!("{:?}", self.0)).into_response() // BAD
    }
}
```

### NOT high — safe

```rust
// Log chi tiết nội bộ, trả client message generic + request id
impl IntoResponse for AppError {
    fn into_response(self) -> Response {
        let id = Uuid::new_v4();
        tracing::error!(error = ?self.0, %id, "request failed"); // chi tiết chỉ vào log
        (StatusCode::INTERNAL_SERVER_ERROR,
         Json(json!({ "error": "internal error", "ref": id }))).into_response()
    }
}
```

## Fix recommendation

1. **Map error sang message generic** cho client; chi tiết chỉ vào `tracing`/log nội bộ.
2. **Gắn request id** vào response + log để trace mà không lộ nội bộ.
3. **Đừng đưa `anyhow`/`eyre` chain vào body** — chúng kèm context + backtrace.
4. **Tắt `RUST_BACKTRACE` ở production** (hoặc chỉ vào log có kiểm soát).
5. **Không `unwrap()`/`expect()` trên đường request** — panic message có thể lộ qua một số setup.

## Cross-references

- Rule `02-sql-injection`: error sqlx lộ SQL string giúp attacker craft injection
- Rule `01-hardcoded-secret`: error có thể echo connection string chứa password
