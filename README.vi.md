<div align="center">

### 🇬🇧 [Read in English → README.md](README.md)

</div>

---

# Thanh Tra — Trình quét bảo mật cho mã nguồn

Thanh Tra là scanner bảo mật CLI-first kiêm skill agent đa nền tảng, quét bảo mật chuyên sâu và phát hiện hơn 20 lỗ hổng bảo mật phổ biến nhất trong mã nguồn. Chạy native trên **Claude Code**, **OpenAI Codex CLI** và **Google Antigravity**.

> Credit: Thanh Tra được phát triển từ skill `vbsec` giấy phép MIT do project gốc của **Bùi Tấn Việt** và **Phan Quốc Hiên** chia sẻ. Bộ rule và nền tảng skill upstream vẫn được ghi nhận credit trong fork này.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Claude Code](https://img.shields.io/badge/Claude%20Code-Skill-blue)](https://docs.claude.com/claude-code)
[![OpenAI Codex](https://img.shields.io/badge/OpenAI%20Codex-Skill-black)](https://developers.openai.com/codex/skills)
[![Google Antigravity](https://img.shields.io/badge/Google%20Antigravity-Skill-orange)](https://antigravity.google/docs/skills)

---

## Giới thiệu

Mã nguồn do AI sinh ra hiện chiếm tỷ trọng đáng kể trong các commit mới của ngành phần mềm. Các trợ lý lập trình hiện đại rất giỏi tạo ra mã nguồn *chạy được*, nhưng chúng vẫn thường xuyên xuất ra mã mắc những lỗi bảo mật kinh điển: Hardcoded Secret, SQL Injection, Broken Access Control, Weak Password Hashing, JWT misuse, CORS misconfiguration. Những lỗi này hiếm khi lộ ra trong kiểm thử chức năng — chúng chỉ lộ ra khi đã xảy ra sự cố.

Thanh Tra đưa quy trình rà soát bảo mật cấp production vào trong vòng lặp lập trình với AI. Skill chạy native trên ba nền tảng — gõ `/thanhtra` trong Claude Code, `$thanhtra` (hoặc `/skills`) trong OpenAI Codex CLI, hoặc đơn giản nói *"scan security cho repo này"* với Google Antigravity — và nhận một báo cáo có cấu trúc rõ ràng, bao phủ hơn 20 nhóm lỗ hổng phổ biến. Thanh Tra cũng có scanner CLI-first qua `bin/thanhtra scan --json`.

Thanh Tra đã được chạy thử trên các ứng dụng mã nguồn mở có chủ đích chứa lỗ hổng dùng cho mục đích đào tạo (như OWASP Juice Shop) — và phát hiện được các lỗ hổng tương ứng với những challenge đã được tài liệu hoá: SQL Injection, NoSQL Injection, JWT misuse, Broken Access Control, Mass Assignment, RCE qua deserialization, và nhiều nhóm khác.

Bộ quy tắc chung áp dụng cho mọi ngôn ngữ lập trình. Các quy tắc chuyên sâu theo ngôn ngữ hiện có cho Go, PHP, TypeScript/JavaScript, Python và Rust, bao phủ các framework phổ biến: React, Vue, Angular, Express, NestJS, Next.js, Django, Flask, FastAPI, SQLAlchemy, Sequelize, Prisma, Mongoose, axum, actix-web, sqlx, diesel.

## Tác giả

- **Bùi Tấn Việt** — CEO, [SePay](https://sepay.vn) & [123HOST](https://123host.vn)
- **Phan Quốc Hiên** — CTO, [SePay](https://sepay.vn) & [123HOST](https://123host.vn)

## Cách thức hoạt động

Thanh Tra được thiết kế xoay quanh một số quyết định kỹ thuật giúp phân biệt nó với các scanner truyền thống chỉ đếm pattern (mẫu chuỗi).

- **Suy luận trước, không chỉ đếm pattern.** Thanh Tra không grep máy móc các chuỗi như `eval(` hay `query(`. Mỗi finding tiềm năng đều được xác minh bằng cách đọc context xung quanh, lần theo luồng dữ liệu (từ L1 — input không tin cậy từ phía người dùng — đến L4 — dữ liệu hệ thống đáng tin), và xác nhận dữ liệu thật sự đi tới một sink nguy hiểm mà không được sanitize. Cách tiếp cận này loại bỏ hiện tượng "báo nhầm" (false positive) tràn lan đặc trưng của các scanner dựa trên regex.

- **Định tuyến theo quy mô.** Phạm vi quét nhỏ (≤20 file ngôn ngữ chính VÀ ≤30 file tổng) được quét trực tiếp trong 30-60 giây. Phạm vi lớn hơn được tự động uỷ quyền cho các sub-agent chạy song song — mỗi sub-agent phụ trách một thư mục cấp một — rồi tổng hợp kết quả tại một điểm trung tâm. Trải nghiệm người dùng không đổi, chỉ có chiến lược thực thi bên trong thay đổi.

- **Uỷ quyền sub-agent cho repo lớn.** Với repo hàng trăm file, Thanh Tra khởi tạo tối đa 3 sub-agent chạy song song thông qua general-purpose agent của Claude Code. Mỗi sub-agent quét một phần file độc lập, và các finding được khử trùng lặp và tổng hợp theo bộ ba `(file, dòng, mã quy tắc)`. Cách này giúp thời gian thực thi có giới hạn ngay cả trên monorepo.

- **Hệ thống quy tắc chuyên sâu theo ngôn ngữ.** Khi Thanh Tra phát hiện ngôn ngữ chính của mã nguồn, nó tự động nạp các quy tắc chuyên sâu cho ngôn ngữ đó để thay thế quy tắc chung. Cơ chế này bắt được những pattern đặc thù của từng framework: NoSQL Injection qua `$where` của Mongoose, XSS qua `bypassSecurityTrustHtml` của Angular, SQL Injection qua template literal của Sequelize, JWT algorithm confusion, Gin debug mode bật trong bản production.

- **Phân loại luồng dữ liệu L1–L4.** Input được phân loại theo mức độ tin cậy. Một câu lệnh `db.query(\`SELECT ${x}\`)` chỉ được báo là lỗi khi `x` xuất phát từ L1 (input do người dùng kiểm soát) và đi tới sink SQL mà không qua tham số hoá. Hằng số, biến môi trường và dữ liệu từ nguồn tin cậy không tạo ra false positive.

- **Một finding, một quy tắc.** Một dòng mã đồng thời vi phạm hai quy tắc (ví dụ IDOR và Race Condition) sẽ tạo ra hai finding riêng biệt — không bao giờ là một finding gắn nhiều mã quy tắc cách nhau bằng dấu phẩy. Quy ước này giữ cho số liệu trung thực, báo cáo có thể kiểm chứng, và phần tóm tắt JSON ở cuối báo cáo có thể đọc được bằng máy.

- **Báo cáo song ngữ.** Tiếng Việt là mặc định; tiếng Anh được chọn bằng `lang=en`. Phần tóm tắt JSON ở cuối báo cáo luôn ở tiếng Anh chuẩn để phục vụ tích hợp với hệ thống CI/CD.

- **Đa nền tảng.** Một bộ rule canonical, ba bản platform variant. Claude Code dùng sub-agent song song cho scan lớn; Codex và Antigravity dùng sequential chunking với output identical. Script `sync-skills.sh` giữ rule đồng bộ trên cả ba.

## Hỗ trợ đa nền tảng

Thanh Tra ship ba bản variant từ một nguồn duy nhất:

| Nền tảng | Folder skill | Vị trí cài đặt | Chiến lược LARGE mode |
|---|---|---|---|
| Claude Code | `skills/thanhtra/` | `~/.claude/skills/thanhtra` | Sub-agent song song (3 concurrent) |
| OpenAI Codex CLI | `skills/codex/thanhtra/` | `~/.agents/skills/thanhtra` | Sequential chunking |
| Google Antigravity | `skills/antigravity/thanhtra/` | `~/.gemini/antigravity/skills/thanhtra` | Sequential chunking |

Cả ba chia sẻ cùng 22 rule, language overlay, chuỗi i18n và format output. Findings identical; chỉ chiến lược thực thi khác. Sequential variant chậm hơn ~3× wall-clock so với parallel mode của Claude Code trên repo lớn, nhưng tạo ra cùng JSON summary và cùng báo cáo Markdown.

Người contribute: sửa rule trong `skills/thanhtra/` (folder canonical của Claude), rồi chạy `./scripts/sync-skills.sh` để propagate sang Codex và Antigravity. File platform-specific (`SKILL.md`, `workflows/large-review*.md`) maintain riêng từng platform.

## Cài đặt

Thanh Tra tự động detect mọi platform hỗ trợ có sẵn trên máy và cấu hình skill. Chạy:

```bash
git clone https://github.com/aspelldenny/thanhtra ~/thanhtra
cd ~/thanhtra
./scripts/install.sh         # auto-detect, cài cho platform có sẵn
./scripts/install.sh --all   # ép cài cho cả 3 platform bất kể detection
```

Cách detect:
- **Claude Code** — binary `claude` trong PATH
- **OpenAI Codex CLI** — binary `codex` trong PATH
- **Google Antigravity** — app tại `/Applications/Antigravity.app` (macOS) HOẶC CLI tool `agy` trong PATH (cài qua menu trong Antigravity IDE)

Antigravity là IDE (như VS Code), không phải CLI. Với user mới chưa cài Antigravity skill nào, folder `~/.gemini/antigravity/skills/` không tồn tại — installer sẽ tự tạo.

Installer symlink folder skill phù hợp vào vị trí của từng platform. Để cập nhật về sau:

```bash
cd ~/thanhtra && git pull
```

(Symlink tự load phiên bản mới; khởi động lại CLI/IDE nếu cần.)

**Cài thủ công cho 1 platform:**

```bash
# Claude Code
ln -sfn ~/thanhtra/skills/thanhtra              ~/.claude/skills/thanhtra

# OpenAI Codex CLI
ln -sfn ~/thanhtra/skills/codex/thanhtra        ~/.agents/skills/thanhtra

# Google Antigravity
ln -sfn ~/thanhtra/skills/antigravity/thanhtra  ~/.gemini/antigravity/skills/thanhtra
```

Verify trên từng platform:

```
Claude Code:   /thanhtra
Codex:         $thanhtra        (hoặc /skills, rồi chọn)
Antigravity:   "scan security cho repo này"  (auto-trigger qua description)
```

Xem [docs/vi/installation.md](docs/vi/installation.md) để biết yêu cầu chi tiết, xử lý sự cố và quy trình cập nhật.

## Sử dụng

Phạm vi mặc định là toàn bộ folder. Đây là thay đổi có chủ đích so với các phiên bản trước và phản ánh đúng cách các đội ngũ thường yêu cầu một đợt rà soát bảo mật.

```bash
/thanhtra                       # quét toàn bộ folder (mặc định)
/thanhtra uncommitted           # chỉ quét thay đổi chưa commit
/thanhtra pr id 42 lang=en      # quét PR số 42, báo cáo tiếng Anh
/thanhtra commit within 7days   # quét các commit trong 7 ngày gần nhất
```

**Chạy được mà không cần git.** Vibe coder thường không `git init` trước khi paste code AI sinh vào folder. Scope mặc định (`/thanhtra`) sẽ walk filesystem trực tiếp khi không có `.git/` — các folder build/vendored thông dụng được loại tự động. Các scope phụ thuộc git (`uncommitted`, `staged`, `commit within`, `commit id`, `pr id`) vẫn cần git repository và sẽ in message gợi ý dùng scope mặc định hoặc init git.

Báo cáo được lưu tại `thanhtra-reports/scan-<timestamp>.md` trong chính folder được quét, phục vụ việc đọc lại, chia sẻ với reviewer và đính kèm vào ticket khắc phục.

Xem [docs/vi/usage.md](docs/vi/usage.md) để biết toàn bộ tuỳ chọn, bao gồm `staged`, quét theo commit cụ thể, và quét pull request qua `gh`.

### CLI pre-scan JSON

Thanh Tra cũng có CLI phase-1 để thu thập evidence cơ học. `./scripts/install.sh` symlink CLI vào `~/.local/bin` nên gọi được `thanhtra` từ bất kỳ repo nào:

```bash
thanhtra scan /path/to/repo --json
thanhtra scan /path/to/repo --json --output /tmp/thanhtra-scan.json
thanhtra scan /path/to/repo --json --no-audit
thanhtra prescan --root . --output .thanhtra-pre-scan.json   # raw evidence — chính là cái agent skill đọc
thanhtra scan /path/to/repo --json --triage                  # thêm verdict LLM (cần ANTHROPIC_API_KEY)
```

`scan` xuất `schema: "thanhtra-scan/v1"`, summary ngắn và raw `evidence`. `prescan` xuất thẳng raw evidence (`thanhtra-pre-scan/v1`) mà agent skill đọc trước khi LLM reasoning. Cả hai cố ý cơ học: audit dependency, mask secret, kiểm Docker exposure, phân loại file, và gom hotspot — CLI là nguồn sự thật duy nhất; script bundled trong skill chỉ là wrapper fallback cho máy chưa có CLI trên PATH.

### LLM triage tùy chọn (verdict headless)

`scan --triage` (hoặc subcommand `thanhtra triage`) cho LLM reasoning trên evidence cơ học — loại false positive, map finding về rule, và ra verdict `PASS`/`WARN`/`FAIL` — mà không cần mở agent. Đây chính là thứ giúp Thanh Tra chạy được trong CI hoặc cron, nơi không ai ngồi gõ `/thanhtra` thủ công.

```bash
# Anthropic (mặc định)
export ANTHROPIC_API_KEY=...
thanhtra scan . --json --triage                    # evidence cơ học + verdict trong một document
thanhtra prescan --root . | thanhtra triage --evidence -   # triage evidence từ stdin

# OpenAI — hoặc bất kỳ endpoint OpenAI-compatible nào
export OPENAI_API_KEY=...
thanhtra scan . --triage --triage-provider openai --triage-model gpt-5.1

# OpenRouter / Groq / Together / Ollama local — cùng adapter, khác base URL
thanhtra scan . --triage --triage-provider openai \
  --triage-base-url https://openrouter.ai/api/v1 --triage-model anthropic/claude-opus-4
```

Tầng triage **tùy chọn và pluggable**, có 2 provider:

- **`anthropic`** (mặc định) — Claude Messages API, model `claude-opus-4-8`. Dùng SDK `anthropic` nếu có, không thì gọi HTTP stdlib (giữ CLI zero-install).
- **`openai`** — bất kỳ endpoint OpenAI-compatible `/chat/completions` nào. Một adapter phủ OpenAI, OpenRouter, Groq, Together, DeepSeek, và server local (Ollama, LM Studio, vLLM) — đặt `--triage-base-url` (hoặc `THANHTRA_TRIAGE_BASE_URL`) và `--triage-model`. Key từ `OPENAI_API_KEY` (hoặc `THANHTRA_TRIAGE_API_KEY`). Xin strict JSON-schema, fallback JSON thuần cho server không hỗ trợ.

Chọn qua `--triage-provider` / `THANHTRA_TRIAGE_PROVIDER`. Triage degrade nhẹ nhàng — không có key thì `scan --triage` vẫn xuất đầy đủ evidence cơ học và ghi `triage_error`.

## Các lỗ hổng Thanh Tra phát hiện

| # | Mã quy tắc | Mức độ cao nhất | Có quy tắc chuyên sâu cho |
|---|---|---|---|
| 1 | `HARDCODED-SECRET` | NGHIÊM TRỌNG | — |
| 2 | `SQL-INJECTION` | NGHIÊM TRỌNG | go, php, typescript |
| 3 | `XSS` | CAO | typescript |
| 4 | `IDOR` | CAO | — |
| 5 | `SLOPSQUATTING` | NGHIÊM TRỌNG | — |
| 6 | `BRUTE-FORCE` | CAO | — |
| 7 | `MASS-ASSIGNMENT` | NGHIÊM TRỌNG | typescript |
| 8 | `INSECURE-DESERIALIZATION` | NGHIÊM TRỌNG | go, php, typescript |
| 9 | `SSRF` | CAO | go, typescript |
| 10 | `PATH-TRAVERSAL` | CAO | — |
| 11 | `CSRF` | CAO | php, typescript |
| 12 | `BROKEN-ACCESS-CONTROL` | NGHIÊM TRỌNG | — |
| 13 | `WEAK-PASSWORD-HASHING` | NGHIÊM TRỌNG | — |
| 14 | `JWT-NONE-ALGORITHM` | NGHIÊM TRỌNG | typescript |
| 15 | `CORS-MISCONFIG` | CAO | typescript |
| 16 | `UNRESTRICTED-FILE-UPLOAD` | NGHIÊM TRỌNG | — |
| 17 | `VERBOSE-ERROR-DEBUG-MODE` | CAO | go, php, typescript |
| 18 | `MISSING-RATE-LIMIT` | CAO | — |
| 19 | `RACE-CONDITION` | CAO | — |
| 20 | `OUTDATED-DEPENDENCY` | CAO | — |
| 21 | `COMMAND-INJECTION` | NGHIÊM TRỌNG | go, php, typescript |

Danh sách hiện tại có 21 quy tắc và sẽ tiếp tục mở rộng.

## Tài liệu

- [Cài đặt](docs/vi/installation.md)
- [Hướng dẫn sử dụng](docs/vi/usage.md)
- [Danh mục quy tắc đầy đủ](docs/vi/rules.md)
- [Đóng góp](docs/vi/contributing.md)
- [Vận hành và bảo trì](docs/vi/maintenance.md)

## Lộ trình

- v0.1 — Bộ quy tắc chung + chuyên sâu Go + PHP + báo cáo song ngữ ✅
- v0.2 — Chuyên sâu TypeScript/JavaScript (Sequelize/Prisma/Mongoose, React/Vue/Angular, Express/NestJS/Next.js) ✅
- v0.3 — Phạm vi mặc định chuyển sang toàn repo, lưu báo cáo cố định, giải thích chi tiết cho từng finding ✅
- v0.4 — Chuyên sâu Python (SQLAlchemy/Django ORM SQLi, pickle/yaml deserialization RCE, Werkzeug debugger, FastAPI/Flask/Django CSRF + CORS, PyJWT algorithms, subprocess shell=True) ✅
- v0.5 — Hỗ trợ đa nền tảng: OpenAI Codex CLI + Google Antigravity (sequential LARGE mode, chia sẻ bộ rule, `install.sh` + `sync-skills.sh`) ✅
- v0.6 — Thanh Tra CLI-first deterministic evidence: `bin/thanhtra scan --json`, parse dependency audit, audit gaps, phân loại file ✅
- v0.7 — Rule #22 PROMPT-INJECTION cho app LLM/agent (direct + context-poisoning); header báo cáo ghi thanh tra viên (model) để so sánh giữa các lần scan ✅
- v0.8 — Tầng LLM triage tùy chọn: `scan --triage` / `thanhtra triage` cho LLM reasoning headless trên evidence (loại false positive, map rule, verdict PASS/WARN/FAIL) qua Claude API, SDK-hoặc-stdlib ✅
- v0.9 (hiện tại) — Provider triage `openai`: một adapter OpenAI-compatible phủ OpenAI, OpenRouter, Groq, Together, DeepSeek, và server local (Ollama/LM Studio/vLLM) qua `--triage-base-url` ✅
- v0.10 (hiện tại) — Overlay Rust: SQLi sqlx/diesel, SSRF reqwest, traversal PathBuf, command injection, error leak (axum/actix) ✅
- v1.0+ — SARIF + GitHub Action (CI gate)

## Miễn trừ trách nhiệm

Thanh Tra là một trình quét tham khảo. Skill bắt được những lỗi phổ biến trong mã nguồn do AI sinh ra, nhưng:

- KHÔNG thay thế cho một đợt rà soát bảo mật chuyên nghiệp do chuyên gia thực hiện
- KHÔNG đảm bảo phát hiện 100% lỗ hổng
- KHÔNG tải dữ liệu CVE trực tuyến (cần chạy `npm audit` / `pip-audit` / `govulncheck` riêng cho mục đích này)

Hãy dùng Thanh Tra như **lớp phòng thủ đầu tiên**, không phải bằng chứng về tính an toàn của hệ thống.

## Giấy phép & Ghi nhận

Phát hành theo [MIT License](LICENSE).

Được xây dựng trên kinh nghiệm bảo mật của [SePay](https://sepay.vn) và [123HOST](https://123host.vn) — hai doanh nghiệp Việt Nam trong lĩnh vực fintech và hosting, vận hành hệ thống production dưới các điều kiện đe doạ thực tế.

© 2026 Bùi Tấn Việt & Phan Quốc Hiên.
