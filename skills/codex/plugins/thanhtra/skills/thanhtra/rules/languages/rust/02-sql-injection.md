---
id: SQL-INJECTION
severity_max: CRITICAL
applies_to: rust
---

# SQL Injection (Rust)

## Intent

Rust web vibe code hay dùng `sqlx`, `diesel`, `sea-orm`, `tokio-postgres`. Các crate này **có** đường an toàn (bind parameter `$1`/`?`, macro `sqlx::query!`), nhưng vibe coder vẫn ghép L1 input vào SQL bằng `format!`/`+` rồi đưa vào API runtime (`sqlx::query(&s)`, `diesel::sql_query(s)`, `conn.query(&s, &[])`). Attacker dump DB, escalate.

Điểm bẫy lớn nhất: **`sqlx::query!` (macro, compile-time checked, an toàn) vs `sqlx::query(&format!(...))` (runtime string, nguy hiểm)** — chỉ khác cái `!` và cách dựng string.

## Khi nào CRITICAL

- L1 input (axum `Path`/`Query`/`Json`, actix `web::Path`/`web::Query`, `req.query_string()`) ghép vào:
  - `sqlx::query(&format!("... {}", x))` / `sqlx::query_as(&format!(...))`
  - `diesel::sql_query(format!(...))`
  - `client.query(&format!(...), &[])` (tokio-postgres) — string động thay vì `$1`
  - `conn.execute(&format!(...), [])` (rusqlite)
- Endpoint trên router public (axum/actix/warp/rocket) không có middleware auth

## Khi nào HIGH (giảm cấp)

- Input trace về config/env (L3) không phải request
- Có whitelist cột trước khi nhét vào `ORDER BY` (cột không bind được bằng `$1`)
- Endpoint chỉ admin (extractor/middleware đã check role)

## Cách reasoning (KHÔNG pattern-match thuần)

1. **Grep** sink: `sqlx::query`, `query_as`, `sql_query`, `.execute(`, `client.query`, `conn.query`, `format!` gần SQL keyword.
2. **Read** handler: trace biến từ extractor (`Path(id): Path<String>`, `Query(q)`, `Json(body)`), `req.match_info()`, `params`.
3. **Phân biệt an toàn / nguy hiểm**:
   - `sqlx::query!("SELECT ... WHERE id = $1", id)` → macro, **an toàn** (kể cả khi `id` là L1).
   - `sqlx::query("SELECT ... WHERE id = $1").bind(id)` → bind, **an toàn**.
   - `sqlx::query(&format!("SELECT ... WHERE id = {}", id))` → **NGUY HIỂM**.
   - `diesel` typed DSL (`users.filter(id.eq(uid))`) → an toàn; `sql_query(format!(...))` → nguy hiểm.
4. **Verify**: có `.bind()` / placeholder `$N` / `?`, hay string đã concat sẵn?

## Search patterns (Rust-specific)

```
# sqlx runtime query với format! (BAD)
sqlx::query(_as)?\s*\(\s*&?format!
\.execute\s*\(\s*&?format!
\.fetch(_all|_one|_optional)?\s*\(\s*&?format!

# diesel raw
diesel::sql_query\s*\(\s*format!
sql_query\s*\(\s*[^)]*\+

# tokio-postgres / rusqlite chuỗi động
client\.(query|execute)\s*\(\s*&?format!
conn\.(query|execute|prepare)\s*\(\s*&?format!

# ORDER BY / cột động
format!\s*\(\s*"[^"]*ORDER BY
```

## Examples

### CRITICAL — flag

```rust
// axum + sqlx — format! vào query runtime
async fn get_user(Path(name): Path<String>, State(pool): State<PgPool>) -> impl IntoResponse {
    let sql = format!("SELECT * FROM users WHERE name = '{}'", name); // L1
    let rows = sqlx::query(&sql).fetch_all(&pool).await.unwrap();     // BAD
    Json(/* ... */)
}
```

```rust
// actix + diesel sql_query
async fn search(q: web::Query<Search>) -> impl Responder {
    let sql = format!("SELECT * FROM items WHERE title = '{}'", q.term); // L1
    diesel::sql_query(sql).load::<Item>(&mut conn)?;                     // BAD
}
```

### NOT critical — safe

```rust
// sqlx macro — compile-time checked + bound
let user = sqlx::query!("SELECT * FROM users WHERE id = $1", id)
    .fetch_one(&pool).await?;

// sqlx runtime + bind
sqlx::query("SELECT * FROM users WHERE id = $1").bind(id).fetch_all(&pool).await?;

// diesel typed DSL
users::table.filter(users::id.eq(uid)).load::<User>(&mut conn)?;
```

```rust
// Whitelist cột cho ORDER BY (không bind được)
let col = match sort.as_str() {
    "name" | "created_at" | "price" => sort.as_str(),
    _ => return Err(bad_request()),
};
let sql = format!("SELECT * FROM products ORDER BY {}", col); // safe vì whitelist
```

## Fix recommendation

1. **Ưu tiên macro `sqlx::query!` / `query_as!`** — kiểm tra SQL lúc compile + bind sẵn.
2. **Runtime query phải `.bind()` với `$1`/`?`**, không bao giờ `format!` giá trị vào SQL.
3. **diesel**: dùng typed DSL; nếu bắt buộc `sql_query`, bind qua `.bind::<Type, _>(val)`.
4. **Cột / ORDER BY**: whitelist bằng `match` hoặc `slices::contains` rồi mới ghép.
5. **DB user least privilege**, bật query log để phát hiện bất thường.

## Cross-references

- Rule `17-verbose-error-debug-mode`: trả `err.to_string()` của sqlx leak SQL + schema
- Rule `07-mass-assignment`: `Json(body)` bind cả field nhạy cảm → cross-check
- Rule `04-idor`: SQLi + thiếu ownership check = nuke DB
