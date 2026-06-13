# Shell Specialization

These rule files override generic rules when Thanh Tra detects the primary language as Shell (`.sh`, `.bash`, `.zsh` — bash/zsh/POSIX sh scripts: build tooling, CI scripts, installers, cron jobs, Claude Code hooks).

## How override works

When Thanh Tra scans a repo and detects primary language `shell`, for each rule id present in BOTH `rules/generic/<id>.md` AND `rules/languages/shell/<id>.md`, the language-specific version REPLACES the generic. Generic rules without a shell override apply as-is.

Override matching is by frontmatter `id`, not filename — convention is to keep the same numeric prefix as the generic counterpart.

## Files in this folder

| File | Rule ID | What it specializes |
|---|---|---|
| `01-hardcoded-secret.md` | HARDCODED-SECRET | Secret literal trong script/rc file, secret lên CLI arg (lộ qua `ps`/history), `set -x` xtrace in token ra CI log, heredoc ghi config chứa secret |
| `10-path-traversal.md` | PATH-TRAVERSAL | Unquoted expansion (SC2086), biến rỗng/unset + `rm -rf` (kiểu Steam bug), join path không chặn `../`, `cd` fail rồi destructive op, tar-slip, thiếu `--` |
| `19-race-condition.md` | RACE-CONDITION | Temp file đoán được (`$$`) + symlink attack, TOCTOU check-then-act, cron chạy chồng không `flock`, cửa sổ create→chmod, thiếu `trap` cleanup |
| `20-outdated-dependency.md` | OUTDATED-DEPENDENCY | `curl \| sh` không pin/checksum, http://, binary tải về chạy không verify, install unpinned trong CI, pin bằng tag mutable thay vì SHA |
| `21-command-injection.md` | COMMAND-INJECTION | `eval`/`sh -c` với biến, **splice biến vào heredoc source của interpreter khác** (python3/osascript/awk), `ssh` double expansion, ghi rc file, backticks |

**Note on the heredoc pattern:** dạng lỗi đặc trưng nhất của shell vibe code là nội suy `$VAR` vào string literal của ngôn ngữ KHÁC qua heredoc không quote delimiter (`python3 <<EOF` ... `'$VAR'` ... `EOF`) — một dấu `'` trong data là thoát literal, chạy thành code. Generic rule không có pattern trỏ thẳng vào dạng này; overlay này có. (Bắt nguồn từ finding thật ở một repo render-pipeline.)

## Trust model là một nửa của overlay này

Shell script đa số là tooling owner-run local → input L3/L4 → severity thường downgrade so với web app. Nhưng phải trace đúng — L1 thật sự của shell là: biến CI sinh từ PR/branch/commit-message của contributor, filename từ thư mục watch/upload, nội dung tải từ network, webhook payload. Mỗi rule ghi rõ tiêu chí downgrade để finding không bị thổi phồng (CRITICAL ảo) cũng không bị bỏ sót (im lặng skip vì "chỉ là script local").

Hai dạng KHÔNG downgrade theo trust level vì không cần attacker:
- biến rỗng/unset trong path `rm -rf` (rule 10) — một lần chạy thiếu env là mất data;
- cron chạy chồng hỏng state (rule 19) — chỉ cần thời gian chạy dài hơn interval.

## Reasoning still applies

Language overrides do NOT skip the L1–L4 data flow analysis. They give MORE PRECISE patterns for shell idioms, but the LLM agent must still:

1. **Grep** với pattern shell-specific
2. **Read** TRỌN script (shell script ngắn — đọc hết, đừng skim theo hotspot; bài học từ chính SKILL.md: miss finding HIGH vì skim shell script)
3. **Trace** biến về nguồn: arg, env, `$(jq ...)`, CI context
4. **Verify** guard: quote, `${VAR:?}`, `set -euo pipefail`, whitelist regex, `<<'EOF'` quoted delimiter, env-var passing, `mktemp`+`trap`, `flock`, checksum verify

## Idioms / contexts covered

- bash/zsh/POSIX sh; heredoc sang `python3`/`node`/`osascript`/`awk`
- CI scripts (GitHub Actions `run:` steps), cron jobs, installers, Claude Code hooks
- macOS specifics: `security` Keychain CLI (fix path), APFS case-insensitivity đã ghi nhận ở rule 12 generic reasoning
- ShellCheck codes nhắc đến khi liên quan (SC2086) — chạy ShellCheck là bổ trợ tốt nhưng không thay thế trace L1–L4
