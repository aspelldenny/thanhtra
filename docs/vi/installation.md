# Cài đặt Thanh Tra

> Thanh Tra là một skill của Claude Code. Cài bằng 2 lệnh.

---

## Mục lục

- [Yêu cầu](#yêu-cầu)
- [Cài đặt](#cài-đặt)
- [Verify](#verify)
- [Cập nhật](#cập-nhật)
- [Gỡ cài đặt](#gỡ-cài-đặt)
- [Sau khi cài: nơi lưu báo cáo và .gitignore](#sau-khi-cài-nơi-lưu-báo-cáo-và-gitignore)
- [Troubleshooting](#troubleshooting)
- [Bước tiếp theo](#bước-tiếp-theo)

---

## Yêu cầu

- **Claude Code** đã cài (CLI hoặc desktop)
- **Một git repository** để scan (Thanh Tra dùng `git` để gather danh sách file theo scope)
- **`gh` CLI** (tùy chọn) — chỉ cần nếu muốn scan PR bằng scope `pr id <n>`

Kiểm tra nhanh:

```bash
claude --version
git --version
gh --version        # (Tùy chọn) cho scope pr id
```

---

## Cài đặt

Chạy 2 lệnh sau trong terminal (ngoài Claude Code):

```bash
git clone https://github.com/aspelldenny/thanhtra ~/thanhtra
ln -sfn ~/thanhtra/skills/thanhtra ~/.claude/skills/thanhtra
```

Giải thích từng lệnh:

1. **`git clone`** — tải repository Thanh Tra về `~/thanhtra` (có thể đổi đích nếu muốn; nhớ điều chỉnh lệnh thứ hai theo).

2. **`ln -sfn`** — tạo symlink từ `~/.claude/skills/thanhtra` sang folder skill trong clone. Claude Code tự động phát hiện mọi thứ dưới `~/.claude/skills/`. Dùng symlink (thay vì copy) nghĩa là `git pull` cập nhật skill tại chỗ, không cần copy lại.

Sau khi chạy 2 lệnh, **khởi động lại Claude Code** để load skill mới.

Hoặc dùng installer trong clone — tự detect cả 3 platform (Claude Code, Codex CLI, Antigravity), symlink skill cho từng cái, và cài luôn CLI `thanhtra` (+ alias `Thanh Tra`) vào `~/.local/bin`:

```bash
cd ~/thanhtra && ./scripts/install.sh
```

Skill ưu tiên gọi CLI `thanhtra` trên PATH cho bước pre-scan deterministic (Step 1.5); script bundled trong skill chỉ là fallback. Dùng `--no-cli` nếu muốn bỏ qua bước cài CLI.

---

## Verify

Sau khi restart Claude Code, gõ:

```
/thanhtra
```

Nếu in ra báo cáo scan (header `# Báo cáo quét bảo mật Thanh Tra`) — cài thành công.

Bạn cũng có thể kiểm tra skill đã load chưa bằng cách gõ `/` trong Claude Code — autocomplete sẽ liệt kê `thanhtra`.

---

## Cập nhật

Để pull phiên bản mới:

```bash
cd ~/thanhtra
git pull
```

Sau đó khởi động lại Claude Code để nó reload skill từ disk.

---

## Gỡ cài đặt

```bash
rm ~/.claude/skills/thanhtra    # gỡ symlink
rm -rf ~/thanhtra                            # xóa source clone (tùy chọn)
```

Khởi động lại Claude Code.

---

## Sau khi cài: nơi lưu báo cáo và .gitignore

Khi bạn chạy `/thanhtra` lần đầu trong một repo, Thanh Tra sẽ tạo file `thanhtra-reports/scan-<timestamp>.md` trong repo đó để lưu báo cáo. Để tránh commit nhầm những file scan này, thêm vào `.gitignore` của project:

```bash
# Thêm vào .gitignore của project được scan:
echo "thanhtra-reports/" >> .gitignore
git add .gitignore && git commit -m "Add thanhtra-reports/ to .gitignore"
```

> ⚠️ Mỗi lần scan, nếu Thanh Tra phát hiện `thanhtra-reports/` chưa có trong `.gitignore`, nó sẽ in một khuyến nghị ở cuối stdout. Thanh Tra **không** tự động sửa `.gitignore` — đó là quyết định của bạn.

Nếu bạn thực sự muốn commit báo cáo (ví dụ: để giữ compliance trail, làm bằng chứng PR review), đơn giản là đừng thêm entry kia. Tên file đã có timestamp nên nhiều lần scan không bị xung đột tên.

---

## Troubleshooting

### `/thanhtra` không xuất hiện trong Claude Code

- Xác nhận symlink tồn tại: `ls -la ~/.claude/skills/thanhtra` phải hiện link trỏ tới `~/thanhtra/skills/thanhtra`.
- Xác nhận target tồn tại: `ls ~/thanhtra/skills/thanhtra/SKILL.md` phải in ra đường dẫn file.
- Khởi động lại Claude Code (đóng và mở lại). Skill discovery chạy lúc startup.

### "Permission denied" khi tạo symlink

Kiểm tra quyền thư mục:

```bash
ls -ld ~/.claude/skills
```

Nếu thư mục chưa tồn tại, tạo nó: `mkdir -p ~/.claude/skills`.

### Nhiều workspace Claude Code

Skills cài trong `~/.claude/skills/` là **global** — áp dụng cho mọi workspace Claude Code bạn mở. Không cần cài per-workspace.

### Scope `pr id <n>` báo `command not found: gh`

Scope PR cần GitHub `gh` CLI:

```bash
# macOS
brew install gh

# Ubuntu/Debian
sudo apt install gh

# Sau đó đăng nhập
gh auth login
```

Workaround: dùng scope khác (`uncommitted`, `staged`, `commit id`, `all`).

### Windows / WSL

Native Windows không được hỗ trợ chính thức. Dùng WSL2 với cùng instructions ở trên (symlink và skill discovery của Claude Code đều hoạt động trong WSL).

---

## Bước tiếp theo

- Đọc [usage.md](usage.md) để biết tất cả scope và cách đọc báo cáo
- Xem [rules.md](rules.md) để hiểu 24 rule
- Muốn đóng góp? Đọc [contributing.md](contributing.md)
