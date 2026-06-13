# Sử dụng Thanh Tra

Hướng dẫn chi tiết cách gọi `/thanhtra`, chọn scope, hiểu báo cáo, và tích hợp vào CI/CD.

> Đã cài skill chưa? Nếu chưa, đọc [installation.md](installation.md) trước.

---

## Mục lục

- [Lệnh cơ bản](#lệnh-cơ-bản)
- [Tất cả scope](#tất-cả-scope)
- [Báo cáo lưu ở đâu](#báo-cáo-lưu-ở-đâu)
- [Chọn ngôn ngữ output](#chọn-ngôn-ngữ-output)
- [Anatomy of a report](#anatomy-of-a-report)
- [JSON summary cho tooling](#json-summary-cho-tooling)
- [Performance expectations](#performance-expectations)
- [Resume khi LARGE mode bị interrupt](#resume-khi-large-mode-bị-interrupt)
- [Tích hợp CI/CD](#tích-hợp-cicd)

---

## Lệnh cơ bản

Mở Claude Code ở thư mục git repo. Trong khung chat:

```
/thanhtra
```

> **⚠️ Thay đổi hành vi ở v0.3:** `/thanhtra` (không kèm tham số) bây giờ quét **toàn bộ repository**. Trước đây mặc định tương đương với `uncommitted`. Nếu muốn hành vi cũ, hãy dùng `/thanhtra uncommitted` hoặc `/thanhtra diff`.

Mặc định Thanh Tra sẽ:
1. Lấy tất cả file trong repo (toàn bộ, không chỉ uncommitted)
2. Detect ngôn ngữ chính (Go/PHP/JS/Python/...)
3. Route SMALL hoặc LARGE mode theo số file
4. Áp 24 rule generic + overlay language (nếu có)
5. In báo cáo Markdown + JSON summary lên stdout
6. Lưu một bản báo cáo vào `thanhtra-reports/scan-<timestamp>.md` trong repo

### CLI JSON mode

Để automation hoặc agent wrapper dùng trực tiếp phần scanner cơ học. `./scripts/install.sh` symlink CLI vào `~/.local/bin` nên chạy được từ bất kỳ repo nào:

```bash
thanhtra scan . --json
thanhtra scan . --json --output /tmp/thanhtra-scan.json
thanhtra scan . --json --no-audit
thanhtra prescan --root . --output .thanhtra-pre-scan.json   # raw evidence — agent skill đọc file này
thanhtra scan . --json --triage                              # thêm verdict LLM (cần ANTHROPIC_API_KEY)
```

`scan` xuất `schema: "thanhtra-scan/v1"`. `summary` ở top-level ổn định cho tooling; `evidence` chứa raw pre-scan payload để LLM agent reasoning ở bước sau. `prescan` xuất thẳng raw evidence (`thanhtra-pre-scan/v1`) — đây là lệnh agent skill gọi ở Step 1.5; script bundled trong skill chỉ là wrapper fallback cho máy chưa có CLI trên PATH.

`--triage` thêm một bước LLM reasoning trên evidence cơ học: loại false positive, map finding về 24 rule canonical, và ra verdict `PASS`/`WARN`/`FAIL` — tương đương chạy skill `/thanhtra` nhưng headless. Default dùng Anthropic Claude API (`claude-opus-4-8`; override bằng `THANHTRA_TRIAGE_MODEL`), cần `ANTHROPIC_API_KEY`, dùng SDK `anthropic` nếu có hoặc gọi HTTP bằng stdlib. Không có key thì `scan --triage` vẫn xuất đầy đủ evidence và ghi `triage_error`. Subcommand `thanhtra triage --evidence <file|->` triage một file prescan/scan JSON có sẵn.

---

## Tất cả scope

| Lệnh | Quét gì |
|---|---|
| `/thanhtra` | **Toàn bộ repo (mặc định — thay đổi ở v0.3)** |
| `/thanhtra uncommitted` | Chỉ thay đổi chưa commit (staged + unstaged) |
| `/thanhtra diff` | Alias của `uncommitted` |
| `/thanhtra staged` | Chỉ file đã `git add` |
| `/thanhtra commit within 7days` | Tất cả file đụng tới trong N ngày qua |
| `/thanhtra commit id <sha>` | File trong 1 commit cụ thể |
| `/thanhtra pr id 42` | File trong PR #42 (GitHub) — cần `gh` CLI |
| `/thanhtra all` | Alias rõ ràng cho toàn bộ repo |

### Ví dụ thực tế

```bash
# Mặc định — quét toàn bộ repo, báo cáo Tiếng Việt, lưu vào file
/thanhtra

# Trước khi commit: chỉ quét những gì đã thay đổi
/thanhtra uncommitted

# Review trước khi merge: scan PR với báo cáo tiếng Anh
/thanhtra pr id 42 lang=en

# Audit định kỳ: scan commit gần đây
/thanhtra commit within 30days

# Tìm báo cáo mới nhất
ls -lt thanhtra-reports/ | head -5

# So sánh 2 lần scan
diff thanhtra-reports/scan-2026-05-13-100000.md thanhtra-reports/scan-2026-05-14-100000.md
```

---

## Báo cáo lưu ở đâu

Từ v0.3 trở đi, **mỗi lần scan Thanh Tra đều lưu một bản báo cáo vào file** ngay trong repo được quét:

- Đường dẫn: `thanhtra-reports/scan-<YYYY-MM-DD-HHMMSS>.md`
- Định dạng tên file: `scan-YYYY-MM-DD-HHMMSS.md` — sort theo thứ tự thời gian tự nhiên
- Nội dung file giống hệt nội dung in ra stdout — file dùng để đọc lại và share, stdout để xem ngay
- Nếu `thanhtra-reports/` chưa có trong `.gitignore`, Thanh Tra sẽ in một khuyến nghị ở cuối stdout — **Thanh Tra không tự sửa `.gitignore`**, việc đó để bạn quyết định
- Báo cáo có thể xóa bất cứ lúc nào, không phải file state

Tìm báo cáo mới nhất:

```bash
ls -lt thanhtra-reports/ | head -5
```

Xem báo cáo gần nhất:

```bash
cat "$(ls -t thanhtra-reports/scan-*.md | head -1)"
```

Xem [installation.md](installation.md#sau-khi-cài-nơi-lưu-báo-cáo-và-gitignore) để thêm `thanhtra-reports/` vào `.gitignore`.

---

## Chọn ngôn ngữ output

Thanh Tra hỗ trợ Tiếng Việt (mặc định) và English. Cách chỉ định:

| Cú pháp | Kết quả |
|---|---|
| (không có flag) | Tiếng Việt |
| `lang=vi` | Tiếng Việt |
| `--vi` | Tiếng Việt |
| `lang=en` | English |
| `--en` | English |

Ví dụ:

```
/thanhtra pr id 42 lang=en
/thanhtra commit within 14days --en
/thanhtra staged
```

**Lưu ý:** Báo cáo Markdown đổi theo lang, NHƯNG:
- Rule ID (HARDCODED-SECRET, SQL-INJECTION...) luôn EN
- File path, code snippet luôn nguyên gốc
- JSON summary ở cuối báo cáo LUÔN dùng EN canonical (để tooling parse ổn định)

---

## Anatomy of a report

Một báo cáo điển hình:

```
# Báo cáo quét bảo mật Thanh Tra

Phạm vi: Thay đổi chưa commit
Số file: 12 (8 .ts, 4 .py)
Ngôn ngữ chính: typescript
Chế độ: NHỎ (quét trực tiếp)
Ngày: 2026-05-13

## KẾT LUẬN: KHÔNG ĐẠT
Có lỗi NGHIÊM TRỌNG. KHÔNG được deploy đến khi sửa hết.

## NGHIÊM TRỌNG (chặn deploy)
| File:Dòng | Loại lỗi | Mô tả | Cách sửa |
|---|---|---|---|
| api/users.ts:42 | SQL-INJECTION | req.body.id ghép vào SQL | Dùng parameterized query |
| .env:1 | HARDCODED-SECRET | STRIPE_KEY=sk_live_... | Xoay key + .gitignore |

## CAO (cần khắc phục)
| auth.ts:18 | WEAK-PASSWORD-HASHING | createHash('md5') | Dùng bcrypt/argon2 |

## TRUNG BÌNH
(không có)

## ĐÃ ĐẠT
- ✓ XSS — Vue auto-escape
- ✓ CORS — Origin cụ thể
- ✓ CSRF — Token có trong form

## JSON Summary
```json
{
  "verdict": "FAIL",
  "scope": "uncommitted",
  "files_scanned": 12,
  "primary_language": "typescript",
  "mode": "SMALL",
  "counts": {"critical": 2, "high": 1, "medium": 0, "low": 0},
  "findings": [
    {"file": "api/users.ts", "line": 42, "rule": "SQL-INJECTION", "severity": "CRITICAL"},
    {"file": ".env", "line": 1, "rule": "HARDCODED-SECRET", "severity": "CRITICAL"},
    {"file": "auth.ts", "line": 18, "rule": "WEAK-PASSWORD-HASHING", "severity": "HIGH"}
  ]
}
```

### Các phần trong báo cáo

| Section | Mục đích |
|---|---|
| Header | Scope đã quét, số file, ngôn ngữ chính, mode (SMALL/LARGE), ngày |
| KẾT LUẬN (Verdict) | PASS / WARN / FAIL — quyết định có deploy được không |
| NGHIÊM TRỌNG | CRITICAL — chặn deploy, fix trước tiên |
| CAO | HIGH — phải fix trước production |
| TRUNG BÌNH | MEDIUM — fix sớm, không block |
| ĐÃ ĐẠT | Rule đã check và pass — minh chứng đã quét đủ |
| JSON Summary | Machine-readable, để CI parse |

### Verdict logic

| Tình huống | Verdict | Ý nghĩa |
|---|---|---|
| ≥1 CRITICAL | **FAIL** | Không được deploy |
| 0 CRITICAL, ≥1 HIGH | **WARN** | Có thể deploy nhưng phải có plan fix |
| 0 CRITICAL, 0 HIGH | **PASS** | OK deploy |

WARN **không** có nghĩa là "approve". Đội security/tech lead vẫn phải review HIGH issues.

---

## JSON summary cho tooling

JSON summary luôn nằm ở cuối báo cáo, trong fenced code block `json`. Schema cố định:

```json
{
  "verdict": "PASS" | "WARN" | "FAIL",
  "scope": "uncommitted" | "staged" | "commit_within_Ndays" | "commit_id_<sha>" | "pr_<num>" | "all",
  "files_scanned": <int>,
  "primary_language": <string>,
  "mode": "SMALL" | "LARGE",
  "counts": {
    "critical": <int>,
    "high": <int>,
    "medium": <int>,
    "low": <int>
  },
  "findings": [
    {
      "file": <string>,
      "line": <int>,
      "rule": <string>,
      "severity": "CRITICAL" | "HIGH" | "MEDIUM" | "LOW"
    }
  ]
}
```

### Parse JSON từ output

Báo cáo là Markdown — extract JSON bằng:

```bash
# Output đã save vào report.md
awk '/^```json$/,/^```$/' report.md | sed '1d;$d' > summary.json
jq '.verdict' summary.json
# "FAIL"
```

Hoặc trong Node.js:

```javascript
const fs = require('fs');
const md = fs.readFileSync('report.md', 'utf8');
const match = md.match(/```json\n([\s\S]*?)\n```/);
const summary = JSON.parse(match[1]);
if (summary.verdict === 'FAIL') process.exit(1);
```

---

## Performance expectations

| Mode | Trigger | Thời gian | Tài nguyên |
|---|---|---|---|
| SMALL | ≤20 file ngôn ngữ chính VÀ ≤30 file tổng VÀ ≤14 ngày | 30-60 giây | 1 agent, ~5-15 tool calls |
| LARGE | Vượt 1 trong 3 ngưỡng trên | 5-15 phút | Spawn sub-agents song song, mỗi chunk 1 agent |

LARGE mode dùng [chunking-strategy.md](../../skill/references/chunking-strategy.md) để chia file theo top-level folder, mỗi sub-agent xử lý 1 chunk. Main agent aggregate findings + translate cuối.

### Khi nào dùng SMALL vs LARGE?

Bạn không cần lo — SKILL.md route tự động. Nhưng nếu muốn ép:

- Scope hẹp hơn (`staged`, `commit id`) → thường SMALL
- Scope rộng (`all`, `commit within 30days`) → LARGE
- Repo nhỏ (<30 file) → luôn SMALL kể cả `all`

---

## Resume khi LARGE mode bị interrupt

LARGE mode dùng `TodoWrite` để track từng chunk. Nếu bạn interrupt giữa chừng (Ctrl+C, sập máy, etc.):

1. Mở lại Claude Code trong cùng thư mục
2. Gọi lại lệnh ban đầu (cùng scope, cùng lang)
3. Skill sẽ thấy thư mục `.thanhtra-tmp/` còn findings cũ → tiếp tục từ chunk chưa xong

**Quan trọng:**
- ĐỪNG xóa `.thanhtra-tmp/` thủ công nếu muốn resume
- Sau khi scan xong, Thanh Tra tự cleanup `.thanhtra-tmp/`
- Thêm `.thanhtra-tmp/` vào `.gitignore` của repo nếu chưa có:
  ```
  .thanhtra-tmp/
  ```

---

## Tích hợp CI/CD

Thanh Tra chạy dưới dạng Claude Code skill (cách A–C) hoặc headless qua CLI (cách D). Chọn một:

### D. SARIF + GitHub code scanning (khuyến nghị, không cần agent)

`thanhtra scan --sarif` xuất SARIF 2.1.0 từ findings *đã triage* (false
positive đã loại), nên findings hiện thẳng trong **Security tab** và annotate
inline trên PR. CI không cần cài Claude Code — chỉ cần Python 3 và một API key.

Copy [`examples/github-actions/thanhtra.yml`](../../examples/github-actions/thanhtra.yml)
vào `.github/workflows/` của repo bạn:

```yaml
name: Thanh Tra security gate
on:
  pull_request:
    branches: [main]
permissions:
  contents: read
  security-events: write
jobs:
  thanhtra:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Install Thanh Tra
        run: git clone --depth 1 https://github.com/aspelldenny/thanhtra.git "$RUNNER_TEMP/thanhtra"
      - name: Scan to SARIF
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
        run: '"$RUNNER_TEMP/thanhtra/bin/thanhtra" scan . --sarif --output thanhtra.sarif'
      - name: Upload to GitHub code scanning
        uses: github/codeql-action/upload-sarif@v3
        with:
          sarif_file: thanhtra.sarif
          category: thanhtra
```

Lưu ý:

- **Chạy lúc nào là quyền của bạn** (mỗi PR / mỗi push / nightly `schedule`) —
  CI minutes và token API triage là quota của bạn.
- `--sarif` tự bật `--triage`; nếu triage không chạy được (thiếu key, lỗi API)
  step sẽ **exit 1** thay vì upload một log rỗng trông như "sạch".
- Muốn chặn merge khi có findings: bật branch protection → "Require code
  scanning results". Mapping severity: CRITICAL/HIGH → `error`,
  MEDIUM → `warning`, LOW → `note`.
- Dùng được mọi provider OpenAI-compatible — xem khối env trong file mẫu
  (`THANHTRA_TRIAGE_PROVIDER`, `THANHTRA_TRIAGE_MODEL`,
  `THANHTRA_TRIAGE_BASE_URL`).

### A. Pre-commit hook (local, mỗi dev tự chạy)

`.git/hooks/pre-commit`:

```bash
#!/usr/bin/env bash
# Yêu cầu Claude Code đã cài + plugin Thanh Tra đã cài (/plugin install Thanh Tra@Thanh Tra)
set -e

REPORT=$(mktemp)
claude --no-stream -p '/thanhtra staged lang=en' > "$REPORT"

VERDICT=$(awk '/^```json$/,/^```$/' "$REPORT" \
  | sed '1d;$d' | jq -r '.verdict' 2>/dev/null || echo "")

case "$VERDICT" in
  FAIL)
    echo "Thanh Tra FAIL — see findings:"
    cat "$REPORT"
    exit 1
    ;;
  WARN)
    echo "Thanh Tra WARN — HIGH issues found, commit allowed but please fix soon."
    ;;
  PASS)
    echo "Thanh Tra PASS"
    ;;
  *)
    echo "Thanh Tra: could not parse verdict, allowing commit"
    ;;
esac
```

**Lưu ý:** Pre-commit chỉ block khi `verdict=FAIL` (có CRITICAL). WARN chỉ cảnh báo.

### B. GitHub Actions (PR check)

`.github/workflows/Thanh Tra.yml`:

```yaml
name: Thanh Tra security scan
on:
  pull_request:
    branches: [main]

jobs:
  scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Install Claude Code
        run: |
          curl -fsSL https://claude.ai/install.sh | bash
          echo "$HOME/.claude/bin" >> $GITHUB_PATH

      - name: Cài plugin Thanh Tra
        run: |
          # Trong Claude Code session: cài marketplace + plugin
          # (Chạy qua `claude --no-stream -p` nếu CI image hỗ trợ,
          # hoặc dùng env var pre-install của Claude Code khi feature này phát hành.)
          mkdir -p ~/.claude/plugins
          # Cách 1: pre-warm bằng cách clone plugin vào cache
          git clone https://github.com/aspelldenny/thanhtra.git ~/.claude/plugins/cache/thanhtra
          # Cách 2 (recommended khi Claude Code CI tooling chín hơn):
          #   claude plugin marketplace add aspelldenny/thanhtra
          #   claude plugin install Thanh Tra@Thanh Tra

      - name: Run Thanh Tra on PR
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          claude --no-stream -p "/thanhtra pr id ${{ github.event.pull_request.number }} lang=en" \
            > Thanh Tra-report.md

      - name: Post comment on PR
        uses: marocchino/sticky-pull-request-comment@v2
        with:
          path: Thanh Tra-report.md

      - name: Fail on CRITICAL
        run: |
          VERDICT=$(awk '/^```json$/,/^```$/' Thanh Tra-report.md \
            | sed '1d;$d' | jq -r '.verdict')
          [ "$VERDICT" = "FAIL" ] && exit 1 || true
```

### C. Polices tùy chỉnh

Bạn có thể parse JSON summary và áp policy riêng:

```bash
# Chỉ block nếu có ≥3 HIGH issues
HIGH_COUNT=$(jq -r '.counts.high' summary.json)
if [ "$HIGH_COUNT" -ge 3 ]; then
  echo "Too many HIGH issues ($HIGH_COUNT). Blocking."
  exit 1
fi

# Hoặc: chỉ block 1 số rule cụ thể
CRITICAL_RULES=$(jq -r '.findings[] | select(.severity=="CRITICAL") | .rule' summary.json)
if echo "$CRITICAL_RULES" | grep -q "HARDCODED-SECRET"; then
  echo "Hardcoded secret detected — blocking deploy."
  exit 1
fi
```

---

## Bước tiếp theo

- Đọc [rules.md](rules.md) để hiểu chi tiết 24 rule
- Muốn thêm rule mới hoặc support ngôn ngữ mới? Xem [contributing.md](contributing.md)
