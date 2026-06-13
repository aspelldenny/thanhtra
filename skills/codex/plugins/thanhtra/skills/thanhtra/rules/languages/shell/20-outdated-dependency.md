---
id: OUTDATED-DEPENDENCY
severity_max: HIGH
applies_to: shell
---

# Outdated / Unpinned Dependency (Shell)

## Intent

Shell script không có lockfile — "dependency" của nó là **những thứ nó tải về và chạy**. Rule này trong context shell map sang supply-chain của script:

1. **`curl | sh`** — tải code từ network chạy thẳng, không pin version, không checksum. Server bị compromise / domain hết hạn / MITM (nếu http) → RCE ngay lần chạy sau. Tệ hơn: server có thể detect `curl | sh` (qua buffering) và serve nội dung KHÁC với khi browser tải về xem.
2. **Tải binary/installer không verify** — `wget X && chmod +x && ./X` không `sha256sum -c`.
3. **Install không pin version** — `npm install -g some-tool`, `pip install tool` trong setup script: mỗi lần chạy lấy latest, hijack package là dính (liên quan rule 05 SLOPSQUATTING).
4. **HTTP thay vì HTTPS** — `curl http://...` MITM được trên mọi network giữa đường.
5. **Pin bằng mutable ref** — tag git (`@v1`) ghi đè được; chỉ commit SHA là immutable. (GitHub Actions cũng cùng bài: `uses: org/action@v1` vs `@<sha>`.)

## Khi nào HIGH

- `curl | sh` / `bash <(curl ...)` từ domain KHÔNG phải vendor chính chủ có uy tín, hoặc qua http://
- Tải binary rồi chạy/`sudo` mà không checksum verify
- Setup script chạy trong CI (lặp lại tự động, không người nhìn) install unpinned

## Khi nào downgrade (MEDIUM/LOW)

- `curl | sh` từ installer chính chủ vendor lớn (rustup.rs, get.docker.com) qua https — vẫn note, vì pattern này dạy thói quen xấu và vendor cũng từng bị compromise → LOW/MEDIUM
- Script chạy tay 1 lần bởi owner (không phải CI lặp) → giảm 1 mức

## Cách reasoning

1. **Grep** theo patterns dưới.
2. **Read**: nguồn tải là ai (vendor chính chủ? gist cá nhân? domain lạ?), https hay http, có version/SHA pin không, có checksum verify không.
3. **Trace**: script này chạy ở đâu — CI lặp tự động (mỗi lần build là 1 lần tin server đó) hay setup tay 1 lần?
4. **Verify**: `sha256sum -c` / `shasum -a 256 -c` có mặt và checksum lấy từ NGUỒN KHÁC file tải (checksum cùng server với binary = vô nghĩa khi server bị chiếm).

## Search patterns (shell-specific)

```
(curl|wget)\b[^|;\n]*\|\s*(sudo\s+)?(ba|z)?sh\b
bash\s+<\(curl
curl\s+http://|wget\s+http://
chmod\s+\+x[^&]*&&[^&]*\./
(npm|pnpm|yarn)\s+(install|add)\s+(-g\s+)?[a-z@][^=<>@]*$   # không có @version
pip3?\s+install\s+(?!.*==)[a-z]                              # không có ==version
git\s+clone\s+(?!.*--depth)                                  # clone rồi chạy code — pin commit?
@v?\d+\b                                                     # tag pin — mutable, note nếu CI
```

## Examples

### HIGH — flag

```bash
# Gist cá nhân, pipe thẳng vào sudo sh — chuỗi tin tưởng = 1 account GitHub
curl -fsSL https://gist.githubusercontent.com/someone/abc123/raw/setup.sh | sudo sh
```

```bash
# http + binary + chạy luôn, zero verify — MITM trên mọi hop
wget http://tools.example-cdn.net/cli-helper && chmod +x cli-helper && ./cli-helper init
```

```bash
# CI: mỗi build install latest — hijack npm package là vào thẳng pipeline
# (.github/workflows hoặc ci-setup.sh)
npm install -g release-helper        # không @version, không lockfile
release-helper publish
```

### NOT critical — safe

```bash
# Pin version + checksum từ nguồn tách biệt, verify trước khi chạy
VERSION="2.4.1"
SHA256="9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08"
curl -fsSLo tool.tar.gz "https://releases.vendor.com/v${VERSION}/tool.tar.gz"
echo "${SHA256}  tool.tar.gz" | shasum -a 256 -c - || exit 1
tar xzf tool.tar.gz
```

```bash
# Package manager + version pin — reproducible
pip install "ruff==0.4.4"
npm install -g "prettier@3.2.5"
```

## Fix recommendation

1. **Đừng `curl | sh`** — tải về file, đọc (hoặc ít nhất checksum), rồi chạy: `curl -o x.sh && sha256sum -c && sh x.sh`.
2. **Pin version mọi install** trong script/CI: `tool==x.y.z`, `pkg@x.y.z`, binary theo release version + SHA256.
3. **Checksum lấy từ nguồn tách biệt** với file tải (docs chính thức, release notes đã đọc) — không curl checksum cùng chỗ.
4. **HTTPS luôn** — `curl -fsSL`, không bao giờ `http://` cho thứ sẽ chạy.
5. **CI**: pin GitHub Actions bằng commit SHA; cache + lockfile cho mọi package manager mà ecosystem hỗ trợ.

## Cross-references

- Rule `05-slopsquatting`: tên package không tồn tại/typo — cùng họ supply chain
- Rule `21-command-injection`: `curl | sh` với URL build từ biến = injection + supply chain
