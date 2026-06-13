# Rust Specialization

These rule files override generic rules when Thanh Tra detects the primary language as Rust.

## How override works

When Thanh Tra scans a repo and detects primary language `rust`, for each rule id present in BOTH `rules/generic/<id>.md` AND `rules/languages/rust/<id>.md`, the language-specific version REPLACES the generic. Generic rules without a Rust override apply as-is.

Override matching is by frontmatter `id`, not filename — convention is to keep the same numeric prefix as the generic counterpart.

## Files in this folder

| File | Rule ID | What it specializes |
|---|---|---|
| `02-sql-injection.md` | SQL-INJECTION | `sqlx::query!` macro (safe) vs `sqlx::query(&format!(...))` (bad), diesel `sql_query` vs typed DSL, tokio-postgres/rusqlite string động, whitelist ORDER BY |
| `09-ssrf.md` | SSRF | `reqwest`/`ureq`/`hyper` với URL từ L1, allowlist `Url::host_str()` tuyệt đối, chặn private/metadata IP, redirect policy |
| `10-path-traversal.md` | PATH-TRAVERSAL | `fs`/`tokio::fs` với path động, bẫy `PathBuf::join/push` với absolute path, `file_name()` + canonicalize + `starts_with`, `tower_http ServeDir` |
| `17-verbose-error-debug-mode.md` | VERBOSE-ERROR-DEBUG-MODE | `{:?}`/`to_string()` của error ra body, `anyhow`/`eyre` chain + backtrace, `RUST_BACKTRACE`, log vs response |
| `21-command-injection.md` | COMMAND-INJECTION | `Command` argv list (safe) vs `sh -c` + `format!` (bad), `tokio::process`, whitelist enum |

## Reasoning still applies

Language overrides do NOT skip the L1–L4 data flow analysis. They give MORE PRECISE patterns for Rust idioms (axum, actix-web, warp, rocket, sqlx, diesel, sea-orm, reqwest, tokio), but the LLM agent must still:

1. **Grep** với pattern Rust-specific
2. **Read** handler/extractor đầy đủ
3. **Trace** L1 (request extractor) → L2 (DB) → L3 (config) → L4 (constant)
4. **Verify** sanitization context (bind `$1`/macro, allowlist, `file_name()` + canonicalize, argv list)

Rust's type system prevents memory data races, but it does NOT prevent logical injection — SQLi, SSRF, path traversal, command injection, and verbose-error leakage are all reachable via the safe-Rust APIs above.

## Frameworks / crates covered

- axum, actix-web, warp, rocket (web)
- sqlx, diesel, sea-orm, tokio-postgres, rusqlite (DB)
- reqwest, ureq, hyper, isahc (HTTP client)
- std::process / tokio::process (commands)
- anyhow, eyre, tracing (errors / logging)
- tower-http (static serving)

## Contributing

To add a new Rust-specific override:

1. Pick a rule id from `rules/generic/`
2. Copy the generic file's frontmatter, change `applies_to: rust`
3. Replace search patterns + examples with Rust idiom
4. Keep the Intent + L1–L4 reasoning approach
5. Test by running `/thanhtra` on a Rust repo with that vulnerability
