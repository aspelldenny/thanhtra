---
id: RACE-CONDITION
severity_max: HIGH
applies_to: shell
---

# Race Condition (Shell)

## Intent

Race trong shell khác race trong web app (không phải double-spend DB) — nó là **filesystem race**:

1. **Temp file đoán được** — `/tmp/out.$$`, `/tmp/build.tmp`: `$$` (PID) đoán được; trên máy multi-user, attacker tạo sẵn symlink `/tmp/out.1234 → /etc/passwd` → script ghi đè file hệ thống với quyền của owner script (root nếu chạy sudo).
2. **TOCTOU check-then-act** — `[ -f "$f" ] || touch "$f"` rồi thao tác: giữa check và act, file có thể bị thay/symlink.
3. **Concurrent runs đụng nhau** — 2 instance cùng append 1 file / cùng ghi state mà không có lock (`flock`) → state hỏng. Hay gặp ở cron job chạy chồng (job trước chưa xong, job sau đã bắt đầu).
4. **Thiếu cleanup `trap`** — temp file sót lại sau crash, lần chạy sau đọc state cũ.

## Trust model

Single-user laptop, script owner-run → dạng 1/2 gần như không có attacker → LOW (hygiene). NHƯNG: script chạy trên **server multi-user / CI shared runner / chạy bằng sudo** → symlink attack là thật → HIGH. Dạng 3 (concurrent cron) không cần attacker — chỉ cần job chạy chồng → đánh giá theo hậu quả hỏng state.

## Khi nào HIGH

- Temp path đoán được + script chạy quyền cao (sudo/root) trên máy có user khác
- Cron/daemon script ghi shared state không có `flock`/lockfile mà hậu quả là mất/hỏng data
- `chmod`/`chown` sau khi tạo file (cửa sổ giữa create và chmod, file world-readable chứa secret)

## Khi nào downgrade (MEDIUM/LOW)

- Máy single-user, script local tooling → LOW
- Có mktemp nhưng thiếu `trap` cleanup → LOW (hygiene)

## Cách reasoning

1. **Grep** theo patterns dưới.
2. **Read**: script chạy ở đâu (local? cron? CI? sudo?) — đọc comment đầu file, README, crontab nếu có.
3. **Trace**: 2 instance chạy đồng thời thì sao? Ai khác ghi được vào `/tmp`?
4. **Verify**: `mktemp` (random, O_EXCL) + `trap 'rm -f "$tmp"' EXIT` + `flock` cho shared state.

## Search patterns (shell-specific)

```
/tmp/[A-Za-z0-9._-]+\.\$\$         # PID-based temp — đoán được
/tmp/[A-Za-z0-9._-]+(\.tmp|\.lock)?["'\s]   # temp path cứng
>\s*/tmp/                           # redirect vào /tmp path tĩnh
\[\s+-[ef]\s+.*\]\s*(&&|\|\|)       # check-then-act
echo\s+.*>>\s*\$?[A-Za-z_/.]+       # append shared file — có lock không?
crontab|cron\.d                     # script được cron gọi → soi concurrent
mktemp                              # CÓ rồi — check thêm trap cleanup
```

## Examples

### HIGH — flag

```bash
# Chạy bằng sudo trên server, temp path đoán được
# attacker: ln -s /etc/cron.d/backdoor /tmp/deploy.$$  (PID brute-force được)
sudo ./deploy.sh
echo "$CONFIG" > /tmp/deploy.$$     # ghi đè file attacker trỏ tới, quyền root
```

```bash
# Cron mỗi phút, job trước có thể chưa xong — 2 instance cùng ghi
# state.json hỏng giữa chừng (write không atomic)
jq ".count += 1" state.json > state.json.tmp && mv state.json.tmp state.json
# KHÔNG có flock — 2 instance cùng đọc count=5, cùng ghi count=6 (mất 1 increment)
```

```bash
# Secret hở trong cửa sổ create→chmod
echo "$API_KEY" > ~/.myapp/credentials    # umask mặc định → world-readable
chmod 600 ~/.myapp/credentials            # quá muộn — đã có cửa sổ đọc được
```

### NOT critical — safe

```bash
# mktemp random + trap cleanup — chuẩn
tmp=$(mktemp) || exit 1
trap 'rm -f "$tmp"' EXIT
generate_report > "$tmp" && mv "$tmp" report.txt   # mv cùng filesystem = atomic
```

```bash
# flock chặn instance chạy chồng
exec 200>/var/lock/myjob.lock
flock -n 200 || { echo "previous run still active"; exit 0; }
update_state
```

## Fix recommendation

1. **`mktemp`** cho mọi temp file (random tên + `O_EXCL`); KHÔNG bao giờ `$$` hay path cứng trong `/tmp`.
2. **`trap 'rm -f "$tmp"' EXIT`** ngay sau mktemp.
3. **`flock`** cho cron/daemon ghi shared state; `flock -n` + exit để skip thay vì chạy chồng.
4. **Atomic write**: ghi vào temp cùng thư mục rồi `mv` (rename là atomic cùng filesystem) — đừng ghi thẳng vào file đích.
5. **`umask 077`** (hoặc `install -m 600`) TRƯỚC khi tạo file chứa secret, không chmod sau.

## Cross-references

- Rule `10-path-traversal`: symlink trong temp dir — cùng họ filesystem attack
- Rule `01-hardcoded-secret`: file credentials world-readable trong cửa sổ chmod
