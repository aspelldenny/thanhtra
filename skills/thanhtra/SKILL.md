---
name: thanhtra
description: Use when scanning code for security vulnerabilities. Use when user says "scan security", "kiểm tra bảo mật", "security audit", "review security", or invokes `/thanhtra`. Auto-delegates to sub-agents for large scans (>20 main-language files OR >30 total OR >14 days). Outputs bilingual reports (vi/en).
userInvocable: true
---

# Thanh Tra — Security Scanner cho Vibe Coders

Quét lỗ hổng bảo mật cho code do AI sinh ra (vibe code). Thanh Tra kế thừa bộ rule MIT từ vbsec upstream, giữ credit tác giả gốc, và bổ sung CLI/core deterministic để agent bớt phụ thuộc reasoning cơ học. Bộ skill này check 22 lỗi bảo mật phổ biến nhất của vibe code, kế thừa kiến trúc SMALL/LARGE mode từ bộ rule production của SePay, tổng quát hóa cross-language (mặc định) + chuyên sâu cho Go/PHP (phase 1).

> Repo: https://github.com/aspelldenny/thanhtra
> License: MIT (sẽ chốt khi public)

## Invocation

| Command | Scope | Mô tả |
|---|---|---|
| `/thanhtra` | **Toàn repo** (default từ v0.3) | Mặc định — quét toàn bộ repo |
| `/thanhtra all` | Toàn repo | Alias explicit của default |
| `/thanhtra uncommitted` | Uncommitted changes | Quét staged + unstaged (cần explicit từ v0.3) |
| `/thanhtra diff` | Uncommitted changes | Alias intuitive cho `uncommitted` |
| `/thanhtra staged` | Staged files only | Pre-commit scan |
| `/thanhtra commit within Xdays` | Recent commits | Quét commit X ngày gần đây |
| `/thanhtra commit id <sha>` | Specific commit | Quét 1 commit |
| `/thanhtra pr id <number>` | Pull request | Quét PR diff (cần `gh` CLI) |

**v0.3 change:** Default scope đổi từ `uncommitted` → `all`. Non-tech user lần đầu chạy không bị confused bởi report rỗng. Để giữ behavior cũ, dùng `uncommitted` hoặc `diff` explicit.

**Lựa chọn ngôn ngữ output (thêm vào bất kỳ scope nào):**
- `lang=vi` hoặc `--vi` → Tiếng Việt (mặc định)
- `lang=en` hoặc `--en` → English

Ví dụ:
```
/thanhtra pr id 42 lang=en
/thanhtra staged --vi
/thanhtra commit within 7days
```

---

## CRITICAL: Cách dùng skill này (cho LLM agent)

**Các pattern bash/grep trong rule files là VÍ DỤ minh họa, KHÔNG phải lệnh chạy literal.**

### Nguyên tắc

1. **Lý luận, không pattern-match thuần** — Hiểu intent bảo mật đằng sau mỗi check, không chỉ tìm chuỗi
2. **Dùng tool phù hợp** — `Grep`, `Read`, `Glob` thay vì bash grep/find
3. **Đọc context đầy đủ** — Khi gặp pattern, READ hàm xung quanh để hiểu đây có thực sự là lỗ hổng không
4. **Phân loại trust level** — Một query có format chuỗi chỉ nguy hiểm nếu data ghép vào là **L1 (untrusted)**

### Phân loại nguồn dữ liệu (L1–L4)

| Level | Nguồn | Tin cậy | Ví dụ |
|---|---|---|---|
| L1 | Input người dùng | **KHÔNG tin** | `req.body`, `$_GET`, `request.params`, HTTP header, file upload |
| L2 | Database | Bán tin | Giá trị từ DB nhưng nguồn gốc là user input |
| L3 | Code nội bộ | Tin | Hardcoded strings, config keys, computed values |
| L4 | Hệ thống | Tin | Env vars, file paths nội bộ, framework constants |

**Key insight:** `f"SELECT ... {x}"` SAFE nếu `x` là L3+. CRITICAL nếu `x` là L1 không qua parameterization.

Tham khảo chi tiết: [`references/data-flow-classification.md`](references/data-flow-classification.md).

---

## Workflow

```
┌─────────────────────────────────────────────────────────────────────┐
│                     Thanh Tra SCAN WORKFLOW                              │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  [Step 0] Parse args                                                 │
│     ├─ Scope (uncommitted/staged/commit/pr/all)                      │
│     └─ Output lang (vi default | en)                                 │
│                  ↓                                                   │
│  [Step 1] Gather files (git)                                         │
│                  ↓                                                   │
│  [Step 1.5] Deterministic pre-scan evidence                          │
│     └─ scripts/thanhtra-pre-scan.py → JSON hot spots + audit outputs    │
│                  ↓                                                   │
│  [Step 2] Detect primary code language                               │
│     └─ Đọc references/language-detection.md                          │
│                  ↓                                                   │
│  [Step 3] Route by size                                              │
│     ┌──────────────────┬──────────────────┐                          │
│     │  SMALL (inline)  │  LARGE (delegate)│                          │
│     │  ≤20 main+≤30tot │  >20 OR >30 OR   │                          │
│     │  AND ≤14d        │  >14 ngày        │                          │
│     └─────┬────────────┴─────────┬────────┘                          │
│           ↓                      ↓                                   │
│   workflows/small-     workflows/large-                              │
│   review.md            review.md                                     │
│                                                                      │
│   Both apply:                                                        │
│     - rules/generic/*.md (22 rules, luôn chạy)                       │
│     - rules/languages/<detected>/*.md (override nếu trùng tên)       │
│                  ↓                                                   │
│  [Step 4] Generate report                                            │
│     ├─ Markdown report (theo lang chọn)                              │
│     └─ JSON summary (canonical EN, ở cuối)                           │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Step 0: Parse Arguments

Dùng Bash tool ĐÚNG MỘT LẦN cho step này (gather files là việc của git, không phải reasoning).

```bash
ARGS="${ARGUMENTS:-}"

# 0) Detect git availability (KHÔNG bắt buộc có git — v0.5.1+)
IS_GIT_REPO=true
git rev-parse --is-inside-work-tree >/dev/null 2>&1 || IS_GIT_REPO=false

# 1) Extract lang flag (default vi)
LANG="vi"
if echo "$ARGS" | grep -qE 'lang=en|--en|\ben\b'; then LANG="en"; fi
if echo "$ARGS" | grep -qE 'lang=vi|--vi'; then LANG="vi"; fi

# 2) Extract scope (strip lang flags first)
SCOPE=$(echo "$ARGS" | sed -E 's/(lang=(vi|en)|--vi|--en)//g' | xargs)

# 3) Gather files
NO_GIT_NOTE=""
case "$SCOPE" in
  "staged"|"uncommitted"|"diff"|"commit within "*|"commit id "*|"pr id "*)
    if [ "$IS_GIT_REPO" = false ]; then
      echo "{msg_scope_needs_git}"
      exit 1
    fi
    case "$SCOPE" in
      "staged")             FILES=$(git diff --cached --name-only) ;;
      "uncommitted"|"diff") FILES=$(git diff --name-only HEAD); [ -z "$FILES" ] && FILES=$(git diff --cached --name-only) ;;
      "commit within "*)    DAYS=$(echo "$SCOPE" | grep -oE '[0-9]+'); FILES=$(git log --since="${DAYS} days ago" --name-only --pretty=format: | sort -u | grep -v '^$') ;;
      "commit id "*)        SHA=$(echo "$SCOPE" | sed 's/commit id //'); FILES=$(git diff-tree --no-commit-id --name-only -r "$SHA") ;;
      "pr id "*)            PR=$(echo "$SCOPE" | sed 's/pr id //'); FILES=$(gh pr diff "$PR" --name-only) ;;
    esac
    ;;
  "all"|"")
    if [ "$IS_GIT_REPO" = true ]; then
      FILES=$(git ls-files)
    else
      # Non-git folder — walk filesystem. Exclude folder system + vendored, GIỮ dot-files
      # như .env (để scan secrets), .htaccess, .gitignore (file thường, không phải folder).
      FILES=$(find . -type f \
        -not -path '*/.git/*' \
        -not -path '*/.next/*' \
        -not -path '*/.nuxt/*' \
        -not -path '*/.venv/*' \
        -not -path '*/.idea/*' \
        -not -path '*/.vscode/*' \
        -not -path '*/node_modules/*' \
        -not -path '*/vendor/*' \
        -not -path '*/dist/*' \
        -not -path '*/build/*' \
        -not -path '*/target/*' \
        -not -path '*/__pycache__/*' \
        -not -path '*/thanhtra-reports/*' \
        2>/dev/null | sed 's|^\./||')
      NO_GIT_NOTE="true"
    fi
    ;;
  *)
    echo "Unknown scope: $SCOPE"
    exit 1
    ;;
esac

# 4) Strip noise (double-protect — vd git ls-files có thể trả file ở submodule vendored)
FILES=$(echo "$FILES" | grep -vE '(^|/)(node_modules|vendor|dist|build|\.next|\.nuxt|target|\.venv|__pycache__|\.git|thanhtra-reports)/' || true)

# 5) Prepare save location (v0.3+)
TIMESTAMP=$(date +"%Y-%m-%d-%H%M%S")
REPORT_DIR="thanhtra-reports"
REPORT_FILE="${REPORT_DIR}/scan-${TIMESTAMP}.md"
mkdir -p "${REPORT_DIR}"

# 6) Check .gitignore (chỉ relevant nếu là git repo)
GITIGNORE_WARNING=""
if [ "$IS_GIT_REPO" = true ]; then
  if [ -f .gitignore ]; then
    grep -qE '^thanhtra-reports/?$' .gitignore || GITIGNORE_WARNING="missing"
  else
    GITIGNORE_WARNING="missing"
  fi
fi

echo "Scope: ${SCOPE:-all (default)}"
echo "Lang: $LANG"
echo "Git repo: $IS_GIT_REPO"
echo "Files: $(echo "$FILES" | wc -l)"
echo "Report file: $REPORT_FILE"
[ "$NO_GIT_NOTE" = "true" ] && echo "Note: non-git folder — scanning all files via find"
[ "$GITIGNORE_WARNING" = "missing" ] && echo "Note: thanhtra-reports/ not in .gitignore — will warn user at end"
```

**Quan trọng:**
- `thanhtra-reports/` được excluded khỏi scan list — không scan chính báo cáo của mình
- Path output `thanhtra-reports/scan-<timestamp>.md` cần được mkdir trước khi scan, để workflows save vào
- **v0.5.1+**: skill chạy được trên cả non-git folder. Default scope (`all`) dùng `find` thay `git ls-files`. Các scope dựa vào git (`staged`, `uncommitted`, `commit within`, `commit id`, `pr id`) BẮT BUỘC git — báo `msg_scope_needs_git` rồi exit.
- Nếu `NO_GIT_NOTE=true`, report header phải in `{msg_no_git_note}` để user biết folder không có git → không lọc theo `.gitignore`.

---

## Step 1.5: Deterministic Pre-Scan Evidence

Trước khi đọc rule/workflow sâu, thu thập evidence ổn định bằng Thanh Tra CLI. Ưu tiên gọi CLI trên PATH; script bundled chỉ là fallback (cùng một engine):

```bash
# Ưu tiên: CLI (cài qua ./scripts/install.sh, symlink vào ~/.local/bin)
thanhtra prescan --root . --output .thanhtra-pre-scan.json

# Fallback khi máy chưa có CLI trên PATH:
python3 <skill_dir>/scripts/thanhtra-pre-scan.py --root . --output .thanhtra-pre-scan.json
```

Nếu dependency audit cần network và command fail vì sandbox, re-run command audit tương ứng theo cơ chế approval của platform. Nếu user yêu cầu no-network/offline, thêm `--no-audit`:

```bash
thanhtra prescan --root . --no-audit --output .thanhtra-pre-scan.json
```

**Vai trò của pre-scan:**
- Tạo inventory + language counts độc lập với trí nhớ agent
- Tạo `schema: "thanhtra-pre-scan/v1"` và `legacy_schema: "thanhtra-pre-scan/v1"` để tool cũ vẫn hiểu
- Gom hot spots theo 22 canonical rule IDs
- Mask secret literal, không in raw secret
- Ghi nhận git-history secret signals
- Chạy `pip-audit`, `npm audit`, `pnpm audit`, `cargo audit` nếu tool có sẵn và parse thành `dependency_vulnerabilities[]`
- Parse advisory warning không phải CVE (vd RustSec `unmaintained`) thành `dependency_warnings[]`
- Ghi `audit_gaps[]` khi thiếu tool, thiếu lockfile, hoặc audit command fail mà không parse được CVE rõ

**Bắt buộc đọc `.thanhtra-pre-scan.json` trước khi scan code.** Dùng evidence để lập priority list và đảm bảo các lần scan cùng repo bắt đầu từ cùng một tập tín hiệu. Pre-scan KHÔNG tự quyết định vulnerability cuối; LLM vẫn phải đọc context, trace L1-L4, và loại false positive.

Trong report JSON summary, thêm `evidence_file: ".thanhtra-pre-scan.json"` và `audit_gaps` nếu tool thiếu/fail.

---

## Step 1: Load i18n Strings

Đọc file i18n tương ứng với `$LANG`:
- `lang=vi` → Read [`references/i18n/vi.md`](references/i18n/vi.md)
- `lang=en` → Read [`references/i18n/en.md`](references/i18n/en.md)

File i18n chứa bảng key→text cho toàn bộ user-facing strings (section headers, severity labels, verdict, fix recommendations templates). Mọi text trong report final phải lấy từ i18n, KHÔNG hardcode.

**Strings KHÔNG bao giờ dịch:** rule ID (SQL-INJECTION, XSS, IDOR...), file path, code snippet, command name (`/thanhtra`).

---

## Step 2: Detect Primary Code Language

Đọc [`references/language-detection.md`](references/language-detection.md) để biết cách detect. Tóm tắt:

1. Count extension trong file list (đã strip vendored): `.go`, `.py`, `.php`, `.js`, `.ts`, `.jsx`, `.tsx`, `.rb`, `.java`, `.rs`, `.cs`
2. Primary lang = lang chiếm ≥30% tổng files
3. Có `rules/languages/<lang>/` → load overlay; không có → chỉ dùng generic
4. Multi-lang repo (cả Go backend + Vue frontend) → load cả 2 overlay

**Hiện hỗ trợ chuyên sâu:** `go`, `php`, `typescript` (gộp JS+TS), `python`. Các lang khác chỉ dùng generic rules.

---

## Step 3: Route by Size

| Điều kiện | Ngưỡng | Mode |
|---|---|---|
| Files ngôn ngữ chính | ≤20 | SMALL |
| Files ngôn ngữ chính | >20 | **LARGE** |
| Tổng files | ≤30 | SMALL |
| Tổng files | >30 | **LARGE** |
| Timespan (chỉ với scope `commit within`) | ≤14 ngày | SMALL |
| Timespan | >14 ngày | **LARGE** |

BẤT KỲ điều kiện nào sang LARGE → dùng LARGE mode.

- **SMALL mode:** Read [`workflows/small-review.md`](workflows/small-review.md) và follow workflow đó (inline, không sub-agent)
- **LARGE mode:** Read [`workflows/large-review.md`](workflows/large-review.md), trở thành **orchestrator only**:
  1. TodoWrite cho từng chunk (resume được nếu interrupt)
  2. Chunk files theo top-level folder (xem [`references/chunking-strategy.md`](references/chunking-strategy.md))
  3. Spawn sub-agents (general-purpose) cho mỗi chunk với prompt từ [`references/sub-agent-prompts.md`](references/sub-agent-prompts.md)
  4. Sub-agents ghi findings ra `.thanhtra-tmp/findings-<chunk>.md` (luôn dùng EN canonical + rule ID)
  5. Main agent aggregate → translate sang `$LANG` → final report
  6. Cleanup `.thanhtra-tmp/` sau khi done

---

## Step 4: Apply Rules

Cho mỗi rule trong `rules/generic/` (01-22):

1. Read rule file → hiểu intent, severity, search patterns gợi ý
2. Apply lên files trong scope (dùng Grep/Read tool)
3. Với mỗi match: trace data flow (L1-L4), phân loại có phải vulnerability thật không
4. Nếu có rule cùng tên (cùng `id`) trong `rules/languages/<detected-lang>/`, **rule chuyên sâu thắng generic** (đè hoàn toàn pattern + reasoning steps cho lang đó).

**22 rules generic:**

| # | ID | Severity max |
|---|---|---|
| 1 | HARDCODED-SECRET | CRITICAL |
| 2 | SQL-INJECTION | CRITICAL |
| 3 | XSS | HIGH |
| 4 | IDOR | HIGH |
| 5 | SLOPSQUATTING | CRITICAL |
| 6 | BRUTE-FORCE | HIGH |
| 7 | MASS-ASSIGNMENT | CRITICAL |
| 8 | INSECURE-DESERIALIZATION | CRITICAL |
| 9 | SSRF | HIGH |
| 10 | PATH-TRAVERSAL | HIGH |
| 11 | CSRF | HIGH |
| 12 | BROKEN-ACCESS-CONTROL | CRITICAL |
| 13 | WEAK-PASSWORD-HASHING | CRITICAL |
| 14 | JWT-NONE-ALGORITHM | CRITICAL |
| 15 | CORS-MISCONFIG | HIGH |
| 16 | UNRESTRICTED-FILE-UPLOAD | CRITICAL |
| 17 | VERBOSE-ERROR-DEBUG-MODE | HIGH |
| 18 | MISSING-RATE-LIMIT | HIGH |
| 19 | RACE-CONDITION | HIGH |
| 20 | OUTDATED-DEPENDENCY | HIGH |
| 21 | COMMAND-INJECTION | CRITICAL |
| 22 | PROMPT-INJECTION | HIGH |

---

## Step 5: Generate Report (v0.3+ — verbose + persistent)

Tham khảo template trong [`references/output-format.md`](references/output-format.md). Quy tắc cốt lõi:

**Verbose level theo severity:**
- **CRITICAL** → bảng overview + full verbose block per finding (Mô tả ngắn + Tại sao nguy hiểm + Hacker khai thác + Code before/after + Đọc thêm)
- **HIGH** → bảng overview + medium block per finding (Mô tả + Tác động + Code fix + Đọc thêm)
- **MEDIUM** → chỉ bảng compact
- **LOW** → chỉ bảng compact

**Layout:**
1. Header block (scope, file count, primary lang, mode, date, **inspector**, lang code)
   - `{header_inspector}` = tên + phiên bản model đang chạy scan này (ví dụ `Claude Opus 4.8`, `GPT-5.5 Codex`). Tự khai theo model thực tế của bạn; nếu không chắc phiên bản chính xác, ghi họ model (`Claude Opus`, `GPT-5 Codex`). Field này để so sánh các lần scan cùng repo do thanh tra viên khác nhau thực hiện.
2. VERDICT + 1-line description + `verdict_scope_note`
3. CRITICAL section (overview table → verbose blocks)
4. HIGH section (overview table → medium blocks)
5. MEDIUM section (compact table)
6. LOW section (compact table)
7. PASSED CHECKS (list)
8. Next steps (1-2 dòng)
9. **Save notification** (path file đã ghi)
10. **Gitignore warning** (nếu cần)
11. Footer + disclaimer
12. JSON summary (canonical EN — không phụ thuộc lang)

**Save-to-file (v0.3+):**

Sau khi render report:

```bash
# Workflow đã chuẩn bị $REPORT_FILE và $GITIGNORE_WARNING ở Step 0
# Ghi TOÀN BỘ report (identical với stdout) vào file:
cat > "$REPORT_FILE" <<'REPORT_EOF'
<full report content here>
REPORT_EOF

# In dòng cuối ra stdout:
echo ""
# LLM thay {key} bằng giá trị từ i18n file đã load ở Step 1 (KHÔNG có shell function tên `i18n`):
echo "📄 {msg_report_saved}: $REPORT_FILE"
[ "$GITIGNORE_WARNING" = "missing" ] && echo "⚠️ {msg_gitignore_warning_title}: {msg_gitignore_warning_text}"
```

LLM agent thực thi bằng Write tool (NOT bash heredoc) để ghi file, sau đó in 1-2 dòng note ra stdout. Nội dung file PHẢI IDENTICAL với output trên stdout.

Mọi section header, severity label, verdict text lấy từ i18n file đã load ở Step 1.

**Dogfood clarity:** Verdict là trạng thái của security gate Thanh Tra theo phạm vi scan, không phải kết luận chất lượng tổng thể của app/dự án. Luôn in `verdict_scope_note` ngay sau verdict description.

---

## Verdict Logic

Verdict chỉ phản ánh policy của Thanh Tra trong phạm vi scan hiện tại; không thay thế audit đầy đủ, pentest, hay quyết định release của owner.

| Điều kiện | Verdict |
|---|---|
| Có ≥1 CRITICAL | **FAIL** |
| Không CRITICAL, có ≥1 HIGH | **WARN** |
| Không CRITICAL, không HIGH | **PASS** |

WARN ≠ approve. Báo cáo cần nêu rõ HIGH issues cần khắc phục trước production.

---

## Cấu trúc skill (cho người contribute)

```
~/.claude/skills/thanhtra/
├── SKILL.md                          # File này
├── workflows/
│   ├── small-review.md               # Inline scan (default cho repo nhỏ-vừa)
│   └── large-review.md               # Sub-agent delegation
├── rules/
│   ├── generic/                      # 22 rules cross-language (bắt buộc apply)
│   │   ├── 01-hardcoded-secret.md
│   │   ├── 02-sql-injection.md
│   │   ├── ... (đến 22)
│   │   ├── 21-command-injection.md
│   │   └── 22-prompt-injection.md
│   └── languages/                    # Override chuyên sâu per language
│       ├── go/                       # GORM, slog, Colly...
│       ├── php/                      # mysqli/PDO, $_GET, eval/include, Laravel CSRF
│       └── README.md                 # Hướng dẫn add language mới
└── references/
    ├── chunking-strategy.md
    ├── sub-agent-prompts.md
    ├── language-detection.md
    ├── data-flow-classification.md
    ├── output-format.md
    └── i18n/
        ├── vi.md
        └── en.md
```

**Thêm rule mới (cross-language):** tạo file số tiếp theo trong `rules/generic/`, frontmatter có `id`, `severity_max`, `applies_to: all`. Update bảng ở Step 4 trong file này.

**Thêm language specialization mới (e.g., Ruby):** tạo `rules/languages/ruby/<rule-id>.md` với cùng `id` như generic — sẽ tự override. Đọc `rules/languages/README.md` để biết template.

---

## Reasoning-First (cốt lõi)

**DO:**
- Đọc full function khi gặp pattern, KHÔNG flag luôn
- Trace nguồn dữ liệu: input → transformations → sink
- Phân loại L1-L4 trước khi flag CRITICAL
- Đọc rule file trước khi áp dụng

**DON'T:**
- Copy bash example chạy thẳng (đó là minh họa)
- Flag mọi `fmt.Sprintf` là SQLi (chỉ flag nếu data là L1 và không parameterize)
- Bỏ qua "but" clauses (nhiều pattern legitimate)
- Skip context (1 dòng grep không đủ để verdict)

**Mục tiêu là hiểu bảo mật, không phải đếm pattern.**
