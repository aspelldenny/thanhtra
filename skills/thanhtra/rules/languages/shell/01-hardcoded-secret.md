---
id: HARDCODED-SECRET
severity_max: CRITICAL
applies_to: shell
---

# Hardcoded Secret (Shell)

## Intent

Shell script là nơi secret rò theo những đường mà rule generic không nhìn thấy:

1. **Literal trong script committed** — `export API_KEY="sk-..."`, `curl -u admin:hunter2` — kinh điển, generic bắt được.
2. **Secret thành CLI argument** — `mysql -p"$DB_PASS"` expand rồi thì password nằm trong **`ps aux` của mọi user trên máy** và đôi khi trong shell history. Kể cả khi giá trị đến từ env var "sạch", việc đưa nó lên command line là leak channel mới.
3. **`set -x` (xtrace) in secret ra log** — debug mode bật xtrace, mọi expansion (kể cả `$TOKEN`) in ra stderr → **CI log lưu vĩnh viễn**. Đây là leak phổ biến nhất trong CI mà vibe code không nhận ra.
4. **Heredoc/`cat > config` nhúng secret** — script setup ghi file config chứa token literal, file đó không vào git nhưng SCRIPT thì có.
5. **rc file persistence** — `echo "export TOKEN=xxx" >> ~/.zshrc` từ installer.

## Khi nào CRITICAL

- Secret literal server-class (API key trả phí, DB password, private key) trong script tracked git
- `set -x` bật (hoặc `bash -x` trong CI config) trong script có thao tác `$TOKEN`/`$PASSWORD` mà log đi ra CI/file lưu lâu
- Heredoc trong script committed chứa token literal

## Khi nào HIGH (giảm cấp)

- Secret qua CLI arg trên máy multi-user / CI shared (`ps` leak) — giá trị bản thân từ env
- `curl -u user:pass` với pass literal nhưng service internal-only

## Khi nào KHÔNG flag

- `export API_KEY="${API_KEY:?}"` — chỉ re-export/validate env, không có giá trị
- Placeholder rõ ràng: `YOUR_KEY_HERE`, `xxx`, `<token>` trong template/docs
- `source .env` khi `.env` đã gitignored (verify bằng `.gitignore` — đừng đoán)
- Public/publishable keys theo thiết kế (Stripe `pk_`, Firebase client config)

## Cách reasoning

1. **Grep** theo patterns dưới (cộng patterns generic — vẫn áp dụng).
2. **Read** dòng match: literal thật hay expansion từ env? `"sk-$VAR"` không phải literal.
3. **Trace** kênh phụ: giá trị có lên command line không (`ps` leak)? `set -x` có bật trong script/CI không?
4. **Verify** gitignore cho file được script ghi ra; verify history nếu nghi đã từng commit.

## Search patterns (shell-specific)

```
export\s+[A-Z_]*(KEY|TOKEN|SECRET|PASS)[A-Z_]*\s*=\s*["'][^$"']
curl\s+[^|;]*-u\s+\S+:\S+
curl\s+[^|;]*-H\s+["']Authorization:\s*(Bearer|Basic)\s+[A-Za-z0-9]
mysql\s+[^|;]*-p["']?[^$\s"']      # -p<literal> không phải -p"$VAR"
(sshpass|openssl)\s+[^|;]*(-p|pass:)[^$]
set\s+-x|bash\s+-x|sh\s+-x         # xtrace — soi script có secret expansion không
>>?\s*~?/\.(zshrc|bashrc|profile|netrc)
cat\s*>\s*\S*(config|credential|secret)\S*\s*<<
```

## Examples

### CRITICAL — flag

```bash
# Literal trong script committed
export OPENAI_API_KEY="sk-proj-Aa1Bb2Cc3..."   # key thật, tracked git
curl -H "Authorization: Bearer ghp_x9y8z7..." https://api.github.com/repos
```

```bash
# set -x trong CI — mọi expansion in ra log lưu vĩnh viễn
set -x                                          # debug bật rồi quên
deploy --token "$DEPLOY_TOKEN"                  # dòng này in NGUYÊN token ra CI log
```

```bash
# Installer ghi secret vào rc file
echo "export NPM_TOKEN=npm_AbC123..." >> ~/.zshrc   # literal trong script committed
```

### NOT critical — safe

```bash
# Validate env, không có giá trị nào trong script
: "${DEPLOY_TOKEN:?set DEPLOY_TOKEN in environment}"
deploy --token-stdin <<< "$DEPLOY_TOKEN"        # qua stdin, không lên ps
```

```bash
# macOS Keychain — secret không bao giờ chạm script/repo
DB_PASS=$(security find-generic-password -a myapp -s db -w)
PGPASSWORD="$DB_PASS" psql -h localhost mydb    # env var, không phải CLI arg
```

## Fix recommendation

1. **Secret chỉ sống trong env / secret manager**: `security` (macOS Keychain), `pass`, 1Password CLI (`op read`), CI secrets. Script chỉ `: "${VAR:?}"`.
2. **Tránh secret trên command line**: dùng stdin (`--password-stdin` của docker login là chuẩn mẫu), env var (`PGPASSWORD`), hoặc file 0600.
3. **`set +x` quanh vùng nhạy cảm** nếu cần xtrace debug: `set +x; use_token; set -x`. Trong GitHub Actions thêm `::add-mask::`.
4. **Đã từng commit secret** → rotate key ngay; xóa file không đủ (còn trong history).
5. File config script ghi ra chứa secret → `umask 077` trước, và confirm gitignore.

## Cross-references

- Rule `19-race-condition`: cửa sổ create→chmod làm file secret world-readable
- Rule `17-verbose-error-debug-mode`: xtrace là "debug mode" của shell
- Rule `21-command-injection`: rc file vừa là persistence sink vừa là nơi rò secret
