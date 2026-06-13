---
id: PATH-TRAVERSAL
severity_max: HIGH
applies_to: shell
---

# Path Traversal (Shell)

## Intent

Trong shell, path traversal gộp 3 lỗi đặc trưng mà ngôn ngữ khác không có:

1. **Unquoted expansion (SC2086)** — `rm -rf $DIR/*`: word splitting + glob biến 1 path thành nhiều arg; path chứa space/`*` phá hủy ngoài ý muốn.
2. **Biến rỗng/unset trong path phá hoại** — `rm -rf "$BUILD_DIR/"` khi `BUILD_DIR` unset = `rm -rf /`. Đây là lỗi NỔI TIẾNG đã xóa trắng máy người dùng thật (Steam Linux bug).
3. **Join path không chặn `../`/absolute** — `cp "assets/$NAME" out/` với `NAME` từ config/input chứa `../../../etc/cron.d/x` hoặc `/etc/passwd`.

Cộng thêm **argument injection**: filename bắt đầu bằng `-` thành flag (`rm $f` với file tên `-rf`) khi thiếu `--`.

## Trust model

Như rule 21: shell script đa số owner-run, path từ config tracked trong repo là L3 → finding thường là **robustness (LOW/MEDIUM)**, không phải lỗ hổng khai thác được từ xa. NHƯNG dạng 2 (biến rỗng + `rm -rf`) nguy hiểm bất kể trust level — không cần attacker, chỉ cần 1 lần chạy thiếu env là mất data → giữ HIGH.

## Khi nào HIGH

- `rm -rf` / `mv` / destructive op trên path chứa biến KHÔNG có guard `${VAR:?}` hoặc check empty
- `cd $DIR` không check fail rồi destructive op tiếp theo (`cd` fail → op chạy ở cwd hiện tại)
- Path component từ L1 (filename upload, entry trong archive, field từ network) join thẳng không validate
- `tar xf` / `unzip` archive từ nguồn ngoài không kiểm tra path entries (tar-slip)

## Khi nào downgrade (MEDIUM/LOW)

- Path component từ L3 (JSON config owner viết, tracked trong repo) → robustness, LOW/MEDIUM
- Có quote đúng nhưng thiếu `--` separator → LOW (chỉ thành vấn đề khi filename lạ)

## Cách reasoning

1. **Grep** sink: `rm -rf`, `mv`, `cp`, `chmod -R`, `chown -R`, `tar`, `unzip`, `rsync --delete`, `find -delete`.
2. **Read** ngược lên: biến trong path đến từ đâu, có thể rỗng/unset không (`set -u` có bật không?).
3. **Trace** component động về L1/L3: arg, `$(jq -r ...)`, `basename` đã áp chưa.
4. **Verify** guard: `${VAR:?}`, `set -euo pipefail`, `cd ... || exit`, realpath-prefix check, regex whitelist.

## Search patterns (shell-specific)

```
rm\s+(-[a-zA-Z]*r[a-zA-Z]*f|-[a-zA-Z]*f[a-zA-Z]*r)\s+.*\$
rm\s+-rf\s+"?\$\{?[A-Z_a-z]+\}?/      # biến đứng đầu path destructive
cd\s+\$[A-Za-z_]                       # cd unquoted/không check fail
(cp|mv|cat|source|\.)\s+[^|;]*\$\w+    # expansion không quote vào path op
\$\([^)]*jq[^)]*\)                     # path lấy từ JSON — trace tiếp
tar\s+(-?x|--extract)                  # extraction — check nguồn archive
[^-]\s\$[A-Za-z_]+(\s|$)               # SC2086 unquoted expansion (lọc tay)
```

## Examples

### HIGH — flag

```bash
# Biến unset = rm -rf "/" — không cần attacker
clean() {
  rm -rf "$BUILD_DIR/"*    # BUILD_DIR chưa set → xóa từ /
}
```

```bash
# cd fail → rm chạy ở thư mục hiện tại
cd $RELEASE_DIR            # unquoted + không || exit; dir không tồn tại → cd fail
rm -rf ./*                 # xóa nhầm cwd (có thể là $HOME)
```

```bash
# Path từ file watch-dir (L1) join thẳng
for meta in incoming/*.json; do
  asset=$(jq -r '.asset' "$meta")     # attacker ghi "../../home/user/.ssh/authorized_keys"
  cp "uploads/$asset" public/         # thoát khỏi uploads/
done
```

### NOT critical — safe

```bash
# Guard bắt buộc non-empty + quote + --
set -euo pipefail
rm -rf -- "${BUILD_DIR:?BUILD_DIR not set}/"*
```

```bash
# Whitelist basename: chặn cả / lẫn ..
asset=$(jq -r '.asset' "$meta")
[[ "$asset" =~ ^[A-Za-z0-9._-]+$ ]] || { echo "bad asset name" >&2; exit 1; }
cp "uploads/$asset" public/
```

## Fix recommendation

1. **`set -euo pipefail`** đầu script — `set -u` chặn cả họ lỗi biến unset.
2. **`${VAR:?msg}`** cho mọi biến nằm trong path của op destructive.
3. **Quote mọi expansion** (`"$VAR"`) + **`--`** trước path args (`rm -rf -- "$p"`).
4. **`cd "$dir" || exit 1`** (hoặc dùng subshell `( cd ... && ... )`).
5. **Whitelist basename** cho component từ ngoài: regex `^[A-Za-z0-9._-]+$` chặn cả `/` và `..`; hoặc so `realpath` với prefix mong đợi.
6. **Archive ngoài**: `tar --no-absolute-names` (GNU mặc định strip `/`), list entries trước khi extract, extract vào dir rỗng dùng riêng.

## Cross-references

- Rule `21-command-injection`: filename `-rf` thành flag — argument injection
- Rule `16-unrestricted-file-upload`: upload + copy theo tên gốc = traversal chain
- Rule `19-race-condition`: temp path đoán được + symlink = ghi đè file ngoài ý muốn
