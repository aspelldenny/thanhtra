# Vận hành và bảo trì Thanh Tra

Tài liệu này dành cho việc dùng Thanh Tra như một lớp trung gian để soi lỗi bảo mật cho repo thật, trước mắt là các dự án nội bộ.

## Mục tiêu

Thanh Tra không thay thế audit chuyên nghiệp. Vai trò thực tế của nó là:

- Quét nhanh repo trước khi deploy hoặc trước khi review sâu.
- Bắt các lỗi phổ biến do AI/code nhanh sinh ra: secret lộ, SQL injection, IDOR, race condition, CORS sai, thiếu rate limit, command injection.
- Tạo report có cấu trúc để mở ticket sửa lỗi.
- Chuẩn hóa cách agent đọc code bảo mật thay vì grep pattern đơn giản.

## Nguyên tắc sở hữu

Repo gốc thuộc tác giả upstream. Khi bảo trì nội bộ:

- Giữ license và attribution gốc.
- Ưu tiên đóng góp ngược nếu thay đổi có ích chung.
- Với rule/workflow riêng cho dự án nội bộ, tách rõ phần local nếu có chứa thông tin nhạy cảm.
- Không commit report scan chứa secret, path production hoặc dữ liệu khách hàng.

## Workflow bảo trì

Mỗi lần sửa rule, reference hoặc workflow:

```bash
cd /Users/nguyenhuuanh/code/Thanh Tra

# Chạy toàn bộ maintenance gate local
./scripts/maintain.sh
```

Khi cần chạy từng bước thủ công:

```bash
cd /Users/nguyenhuuanh/code/Thanh Tra

# 1. Sửa canonical skill trước:
#    skills/thanhtra/...

# 2. Sync phần dùng chung sang Codex và Antigravity
./scripts/sync-skills.sh

# 3. Validate cấu trúc skill
./scripts/validate-skill.sh

# 4. Validate fixture regression corpus
./scripts/validate-fixtures.sh

# 5. Cài lại hoặc dùng symlink hiện có
./scripts/install.sh --dry-run
```

Nếu bước validate fail, không dùng bản đó để scan repo production.

## Quy trình scan repo thật

Với mỗi dự án cần soi:

```bash
cd /path/to/project

# Scan toàn repo
$thanhtra all lang=vi

# Scan thay đổi đang làm
$thanhtra uncommitted lang=vi

# Scan trước commit
$thanhtra staged lang=vi
```

Sau khi có report:

1. Sửa `CRITICAL` trước.
2. Sửa `HIGH` trước khi deploy production.
3. Với `MEDIUM`/`LOW`, gom thành backlog có owner.
4. Re-scan sau khi sửa để xác nhận.
5. Nếu phát hiện false positive hoặc miss rõ ràng, cập nhật rule tương ứng trong canonical skill rồi chạy lại workflow bảo trì.

## Cadence đề xuất

| Tần suất | Việc cần làm |
|---|---|
| Mỗi lần sửa skill | Chạy `./scripts/maintain.sh` |
| Trước deploy lớn | Scan `all` trên repo production |
| Trước merge nhánh nhạy cảm | Scan `uncommitted` hoặc `staged` |
| Hàng tuần | Cập nhật dependency/advisory notes cho rule `OUTDATED-DEPENDENCY` |
| Hàng tháng | Review false positive/false negative từ các repo đã scan |
| Hàng quý | Thêm fixture test cho rule/language mới |

## Hướng nâng cấp tiếp theo

Ưu tiên theo thứ tự:

1. Mở rộng fixture cho đủ 22 rule.
2. Thêm manifest machine-readable cho rule ID, severity và language overlay.
3. Tích hợp scanner phụ trợ như `gitleaks`, `pnpm audit`, `pip-audit`, `govulncheck`, `osv-scanner` để bổ sung bằng chứng, không thay thế reasoning của agent.
4. Tạo wrapper nội bộ để scan nhiều repo và gom report theo dự án.

## Definition of done cho một nâng cấp rule

- Rule generic hoặc overlay có frontmatter hợp lệ.
- Có ví dụ unsafe và safe.
- Có reasoning giảm false positive.
- Docs rule catalog được cập nhật nếu thay đổi public behavior.
- Đã sync sang Codex/Antigravity.
- `./scripts/validate-skill.sh` pass.
- `./scripts/validate-fixtures.sh` pass.
- Đã scan thử ít nhất một repo hoặc fixture nhỏ.
