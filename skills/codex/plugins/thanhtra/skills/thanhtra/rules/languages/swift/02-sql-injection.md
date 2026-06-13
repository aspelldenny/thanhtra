---
id: SQL-INJECTION
severity_max: CRITICAL
applies_to: swift
---

# SQL Injection (Swift)

## Intent

App Swift hay dùng SQLite local qua **GRDB**, **FMDB**, **SQLite.swift**, hoặc gọi thẳng **sqlite3 C API**; Core Data thì có **NSPredicate**. Các lớp này đều có đường an toàn (bind `?`, SQL interpolation của GRDB, `%@` của NSPredicate), nhưng vibe coder vẫn ghép input bằng string interpolation `\(...)` rồi đưa vào API nhận raw String.

Bẫy lớn nhất của GRDB: **`db.execute(literal: "... \(name)")` (SQLLiteral interpolation → tự bind, AN TOÀN) vs `db.execute(sql: "... \(name)")` (String thuần → nguy hiểm)** — chỉ khác tên argument label.

Lưu ý severity context: DB thường là SQLite local của chính user, nên impact mặc định thấp hơn server. Leo lên CRITICAL khi input đến từ **ngoài user** (deep link, push payload, nội dung sync từ server/user khác, file import) — lúc đó attacker khác đọc/sửa được data local (message history, token cache) của nạn nhân. Swift server-side (Vapor/Fluent + Postgres) thì CRITICAL như web thường.

## Khi nào CRITICAL

- Input L1 từ ngoài user (URL deep link `components.queryItems`, push `userInfo`, JSON server, nội dung chat/file import) ghép vào:
  - `db.execute(sql: "... \(x)")` / `try String.fetchAll(db, sql: "... \(x)")` (GRDB, label `sql:`)
  - `database.executeQuery("... '\(x)'", ...)` / `executeUpdate` (FMDB)
  - `sqlite3_exec(db, "... \(x)", ...)` / `sqlite3_prepare_v2` với string đã ghép
  - `NSPredicate(format: "name == '\(x)'")` — predicate injection, đổi được điều kiện fetch
- Vapor/Fluent server-side: `SQLQueryString` ghép interpolation từ `req.parameters`/`req.query`

## Khi nào HIGH / MEDIUM (giảm cấp)

- Input là text user gõ trong chính app, DB local chỉ chứa data của user đó → MEDIUM (corrupt data chính mình; vẫn flag vì pattern sẽ bị copy-paste sang chỗ khác)
- Cột/`ORDER BY` động đã whitelist bằng `switch`/`Set.contains` → không flag
- Input trace về constant/enum trong app (L4) → không flag

## Cách reasoning (KHÔNG pattern-match thuần)

1. **Grep** sink: `execute(sql:`, `fetchAll(`, `fetchOne(`, `executeQuery`, `executeUpdate`, `sqlite3_exec`, `sqlite3_prepare`, `NSPredicate(format:`.
2. **Read** function chứa sink, xác định string đưa vào có interpolation `\(...)` hay concat `+` không.
3. **Phân biệt an toàn / nguy hiểm (GRDB là chỗ dễ nhầm nhất)**:
   - `db.execute(literal: "UPDATE ... \(name)")` → SQLLiteral interpolation, **tự bind, an toàn**.
   - `db.execute(sql: "UPDATE ...", arguments: [name])` → bind, **an toàn**.
   - `db.execute(sql: "UPDATE ... \(name)")` → String interpolation vào raw SQL, **NGUY HIỂM**.
   - `NSPredicate(format: "name == %@", x)` → placeholder, **an toàn**; `format: "...\(x)..."` → **nguy hiểm**.
4. **Trace nguồn input**: từ deep link/push/server (L1) hay TextField của chính user? Quyết định CRITICAL vs MEDIUM.

## Search patterns (Swift-specific)

```
# GRDB — label sql: với interpolation (BAD); label literal: là safe
\.execute\(sql:\s*"[^"]*\\\(
fetch(All|One|Set)\([^,]+,\s*sql:\s*"[^"]*\\\(

# FMDB
execute(Query|Update)\("[^"]*\\\(

# sqlite3 C API
sqlite3_(exec|prepare_v2?)\([^,]+,\s*"[^"]*\\\(

# NSPredicate format string động
NSPredicate\(format:\s*"[^"]*\\\(

# Concat kiểu cũ
"SELECT|"INSERT|"UPDATE|"DELETE[^"]*"\s*\+
```

## Examples

### CRITICAL — flag

```swift
// GRDB — interpolation vào label sql: (raw String)
func search(term: String, db: Database) throws -> [Item] {
    // term đến từ deep link myapp://search?q=...   (L1)
    try Item.fetchAll(db, sql: "SELECT * FROM item WHERE title = '\(term)'")  // BAD
}
```

```swift
// NSPredicate format động — đổi được điều kiện fetch
let request = NSFetchRequest<Message>(entityName: "Message")
request.predicate = NSPredicate(format: "thread == '\(threadID)'")  // BAD: threadID từ push payload
```

```swift
// sqlite3 C API string ghép
let sql = "DELETE FROM cache WHERE key = '\(key)'"   // key từ server JSON (L1)
sqlite3_exec(db, sql, nil, nil, nil)                  // BAD
```

### NOT critical — safe

```swift
// GRDB literal: — SQL interpolation tự bind
try db.execute(literal: "UPDATE player SET name = \(name) WHERE id = \(id)")

// GRDB arguments
try Item.fetchAll(db, sql: "SELECT * FROM item WHERE title = ?", arguments: [term])

// GRDB query interface (typed, như diesel DSL)
try Item.filter(Column("title") == term).fetchAll(db)

// NSPredicate placeholder — %@ tự escape
request.predicate = NSPredicate(format: "thread == %@", threadID)
```

```swift
// ORDER BY whitelist bằng switch
let col: String
switch sort {
case "name", "createdAt", "price": col = sort
default: throw AppError.badRequest
}
let sql = "SELECT * FROM product ORDER BY \(col)"   // safe vì whitelist
```

## Fix recommendation

1. **GRDB**: ưu tiên query interface (`filter`/`Column`); raw SQL thì dùng label `literal:` hoặc `arguments:` — đừng bao giờ interpolation vào label `sql:`.
2. **FMDB**: `executeQuery("... ?", values: [x])`.
3. **sqlite3 C API**: `sqlite3_prepare_v2` + `sqlite3_bind_text/int`, không ghép string.
4. **NSPredicate**: luôn `%@`/`%d` placeholder; field name động thì whitelist bằng `%K` + check.
5. **Vapor/Fluent**: dùng Fluent query builder; raw SQL qua `SQLQueryString` bind parameters.

## Cross-references

- Rule `09-ssrf`: cùng nguồn L1 deep link/push — một input điều khiển cả URL lẫn SQL
- Rule `01-hardcoded-secret`: DB local chứa token cache → SQLi local đọc được token
- Rule `17-verbose-error-debug-mode`: print lỗi SQLite ra UI leak schema
