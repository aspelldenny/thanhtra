# LARGE Review Workflow

Sub-agent delegation workflow cho repo lớn (>20 main-lang files HOẶC >30 total HOẶC >14 ngày). Main agent trở thành **orchestrator only** — không tự quét, delegate cho sub-agents.

> Được gọi từ [`../SKILL.md`](../SKILL.md) Step 3 khi routing quyết định LARGE mode.

## Inputs (đã có sẵn từ SKILL.md context)

- `$SCOPE`, `$LANG`, `$FILES`, `$PRIMARY_LANG`, `$OVERLAY_AVAILABLE`, i18n strings — same as SMALL mode
- `.thanhtra-pre-scan.json` — deterministic evidence từ Thanh Tra CLI (`thanhtra prescan`, fallback `scripts/thanhtra-pre-scan.py`)

## Steps

### Step L1 — Load pre-scan evidence

Đọc `.thanhtra-pre-scan.json` trước khi chunk scan. Dùng các field sau để ưu tiên chunk và tránh drift giữa các lần scan:

- `secret_hits_masked`
- `git_secret_signals`
- `docker_exposures`
- `dependency_vulnerabilities`
- `dependency_audits`
- `hotspots_by_rule`

Pre-scan evidence KHÔNG tự là finding cuối, trừ dependency audit tool output có CVE/package/version rõ ràng. Mọi hotspot code vẫn phải đọc context và trace L1-L4.

### Step L2 — Setup workspace

1. Tạo workspace tạm cho findings:
   ```bash
   mkdir -p .thanhtra-tmp
   ```

2. Đảm bảo `.thanhtra-tmp/` trong `.gitignore` (warn user nếu không, nhưng vẫn proceed).

### Step L3 — Chunk files

Đọc [`../references/chunking-strategy.md`](../references/chunking-strategy.md) và apply algorithm.

Output: list `chunks` với format:
```
chunks = [
  {"name": "api/handlers", "slug": "api-handlers", "files": [...], "count": 12},
  {"name": "frontend/src/components", "slug": "frontend-components", "files": [...], "count": 25},
  ...
]
```

`slug` = `name` với `/` thay `-`, dùng cho file output.

Ưu tiên xử lý chunk có file xuất hiện trong `.thanhtra-pre-scan.json` trước. Nếu cùng thứ tự, giữ chunking strategy mặc định.

### Step L4 — Create progress tasks (TodoWrite)

Cho mỗi chunk, TodoWrite 1 task:
```
{
  "content": "Scan chunk: <chunk.name> (<count> files)",
  "activeForm": "Scanning chunk: <chunk.name>",
  "status": "pending"
}
```

Lý do: nếu session bị interrupt, user re-run `/thanhtra` → main agent thấy TodoWrite có pending tasks → resume từ chunk chưa scan.

### Step L5 — Spawn sub-agents

Đọc [`../references/sub-agent-prompts.md`](../references/sub-agent-prompts.md) để biết template prompt.

**Spawn parallel (tối đa 3 sub-agents cùng lúc)** — call Agent tool nhiều lần trong 1 message:

```
Agent(subagent_type="general-purpose", description="Thanh Tra scan chunk: api/handlers", prompt=<filled template>)
Agent(subagent_type="general-purpose", description="Thanh Tra scan chunk: frontend/components", prompt=<filled template>)
Agent(subagent_type="general-purpose", description="Thanh Tra scan chunk: shared/utils", prompt=<filled template>)
```

Đợi 3 sub-agents return, update TodoWrite (in_progress → completed), spawn batch tiếp theo.

**Lưu ý quan trọng:**
- Sub-agent KHÔNG có context conversation hiện tại → prompt phải self-contained (xem template trong `sub-agent-prompts.md`)
- Prompt phải include hot spots liên quan chunk lấy từ `.thanhtra-pre-scan.json`; sub-agent scan hot spots đó trước, rồi rà phần còn lại.
- Sub-agent ghi findings ra `.thanhtra-tmp/findings-<chunk-slug>.md` (path tuyệt đối từ repo root)
- Sub-agent return text "FINDINGS_WRITTEN: <path>" — main agent verify file tồn tại

### Step L6 — Handle sub-agent failures

Khi sub-agent return mà:
- File `.thanhtra-tmp/findings-<slug>.md` không tồn tại
- Hoặc file rỗng / không parse được
- Hoặc sub-agent return error

→ **Re-spawn 1 lần** với prompt nhấn mạnh format. Nếu vẫn fail:
- Mark TodoWrite task = `failed: <chunk_name>`
- Continue với chunks khác
- Note trong final report: `"Chunk <name> failed to scan — manual review recommended"`

### Step L7 — Aggregate findings

Đọc tất cả `.thanhtra-tmp/findings-*.md`:

1. **Parse** mỗi file thành list findings (file/line/rule_id/severity/issue/fix/context)
2. **Validate rule_ids**: Mọi finding phải có `rule_id` trong 24 canonical IDs. Nếu sub-agent đã invent (vd `INSECURE-COOKIE`) → map về canonical theo mapping table trong [`../references/sub-agent-prompts.md`](../references/sub-agent-prompts.md#rule-id-discipline-critical--read-carefully). Nếu thật sự không map được → drop hoặc move vào `## NOT_MAPPED` section riêng.
3. **Dedup**: key = `(file, line, rule_id)`. Giữ entry có severity cao nhất. Nếu tie, giữ entry có `context` dài hơn.
   - **Lưu ý:** dedup key có `rule_id` → 1 vị trí (file:line) dính 2 rule khác nhau (vd IDOR + RACE) sẽ là 2 entry riêng, KHÔNG dedup.
4. **Collect NOT_MAPPED**: nếu có findings trong `## NOT_MAPPED` section của sub-agent reports, collect lại để note ở cuối main report (giúp roadmap future rules).
5. **Collect PASSED**: union các rule_id xuất hiện trong `## PASSED` section của tất cả chunks. Một rule chỉ vào PASSED list nếu **không** xuất hiện trong findings của bất kỳ chunk nào.
6. **Cross-chunk rules**:
   - **SLOPSQUATTING**: collect tất cả import statement từ chunks, dedup, kiểm tra package có hợp lệ. Add findings nếu có suspicious.
   - **OUTDATED-DEPENDENCY**: ưu tiên `dependency_vulnerabilities` trong `.thanhtra-pre-scan.json`; nếu có `dependency_warnings` (vd unmaintained/notice), cân nhắc MEDIUM/LOW supply-chain finding theo exploitability; nếu rỗng nhưng audit tool có stdout, đọc `dependency_audits`; nếu tool missing/fail, đọc file dependency lock (`package-lock.json`, `go.sum`, `composer.lock`, `Cargo.lock`) ở root → check static list và ghi audit gap.
   - **CSRF middleware global**: nếu phát hiện middleware global ở 1 chunk, downgrade các CSRF finding ở chunk khác (vì middleware đã apply).

7. **Counts sanity check** (BẮT BUỘC trước khi render):
   ```
   total = len(findings)
   assert total == count_by_severity('CRITICAL') + count_by_severity('HIGH') + count_by_severity('MEDIUM') + count_by_severity('LOW')
   if rendering top_rules_by_count:
       assert total == sum(top_rules_by_count[].count)
   ```
   Nếu fail → có bug ở dedup hoặc rule_id (multi-rule trong 1 finding). Re-check, fix, re-validate.

### Step L8 — Translate (if lang=vi)

Nếu `$LANG = "vi"`:

Với mỗi finding:
- `issue` (EN) → translate sang vi, giữ technical terms tiếng Anh (function name, library, code snippet)
- `fix` (EN) → ưu tiên dùng phrase template từ `i18n/vi.md` (vd "Use parameterized query" → "Dùng parameterized query / prepared statement")

Section headers, verdict labels — lấy từ i18n key đã load.

### Step L9 — Render report (v0.3+ verbose)

Theo template trong [`../references/output-format.md`](../references/output-format.md).

Thêm 1 dòng vào header nếu có chunk failed:
```
**{header_mode}:** {mode_large} ({n_chunks} chunks, {n_failed} failed)
```

**Verbose level theo severity (v0.3+):**
- CRITICAL → overview table + full verbose block (Mô tả ngắn + Tại sao nguy hiểm + Attack scenario + Code before/after + Đọc thêm)
- HIGH → overview table + medium block (Mô tả + Tác động + Code fix + Đọc thêm)
- MEDIUM → compact table only
- LOW → compact table only

**Main agent generates verbose content (non-tech friendly):**

Sub-agents returned compact findings (file, line, rule_id, severity, issue, fix, context). Main agent KHÔNG cần sub-agent trả về verbose content (sub-agent prompt giữ lean). Khi render, main agent paraphrase từ rule file content (đã Read trong Step L1):
- `why_dangerous` → từ section "Intent" + "Examples CRITICAL" của rule
- `attack_scenario` → kịch bản thực tế dựa trên rule's pattern + sub-agent's `context`
- `code_before` → từ sub-agent's `context` (đã có snippet thực)
- `code_after` → từ section "Fix recommendation" của rule, adapt cho code thực tế của finding

Khi translate sang `$LANG=vi`: dịch text, giữ code English. Khi `lang=en`: dùng EN canonical.

### Step L9.5 — Save report to file (v0.3+)

1. Render full report (theo Step L8 logic)
2. **Save** dùng Write tool:
   - Path: `thanhtra-reports/scan-<TIMESTAMP>.md` (đã prepare ở SKILL.md Step 0)
   - Nội dung IDENTICAL với stdout
3. **Print stdout** sau report:
   ```
   📄 {msg_report_saved}: thanhtra-reports/scan-2026-05-13-143022.md
   ```
4. **If gitignore warning needed:**
   ```
   ⚠️ {msg_gitignore_warning_title}: {msg_gitignore_warning_text}
   ```

### Step L10 — Determine verdict

| Findings | Verdict |
|---|---|
| ≥1 CRITICAL | FAIL |
| 0 CRITICAL, ≥1 HIGH | WARN |
| 0 CRITICAL, 0 HIGH | PASS |

Nếu có chunk failed → downgrade verdict 1 cấp (PASS→WARN, WARN→FAIL) hoặc giữ FAIL, kèm note.

### Step L11 — Cleanup

```bash
rm -rf .thanhtra-tmp    # cleanup sub-agent temp files (luôn xóa)
# KHÔNG xóa thanhtra-reports/ — đó là persisted output cho user
```

**Quan trọng (v0.3+):** Chỉ xóa `.thanhtra-tmp/` (chứa raw findings từ sub-agents). KHÔNG được xóa `thanhtra-reports/` — đó là output user cần re-read/share.

Update TodoWrite: mark tất cả tasks `completed`.

## Resume protocol

Nếu user re-run `/thanhtra` trong khi có TodoWrite pending từ lần trước:

1. Đọc TodoWrite — xác định chunks `pending` / `in_progress`
2. Đọc `.thanhtra-tmp/` — chunks nào đã có `findings-*.md` thì coi như đã scan
3. Chỉ spawn sub-agent cho chunks chưa có findings file
4. Aggregate như bình thường (Step L6)

Nếu user muốn re-scan từ đầu: dùng arg `/thanhtra ... --fresh` → xóa `.thanhtra-tmp/` + TodoWrite trước khi bắt đầu.

## Performance target

| Chunks | Sub-agents | Sub-agent time | Wall time (3-parallel) |
|---|---|---|---|
| 5 | 5 | ~1 min mỗi | ~2 min |
| 10 | 10 | ~1 min mỗi | ~4 min |
| 15 | 15 | ~1-2 min mỗi | ~5-10 min |

Main agent context: ~30-60K tokens (orchestration + aggregate). Sub-agent context riêng (mỗi cái ~30K).

## Edge cases

| Scenario | Handling |
|---|---|
| Chunk có 1 file rất lớn (>5000 dòng) | Sub-agent đọc bằng Grep trước → Read targeted sections. OK. |
| 2 chunks cùng tìm thấy lỗi trong file giống nhau (file ở biên) | Dedup ở Step L6 |
| Sub-agent output JSON thay vì markdown | Re-spawn với prompt nhấn mạnh format |
| Generated code chiếm cả 1 chunk | Sub-agent flag tự "this chunk is mostly generated, low priority". Main agent giảm severity các finding trong chunk này 1 cấp. |
| Repo 500+ file → 15 chunk, mỗi chunk 30+ file | Vẫn OK, sub-agent đủ context. Time ~10-15 phút. |
| User Ctrl+C giữa chừng | TodoWrite + `.thanhtra-tmp/` giữ lại. Re-run → resume từ chunk dở dang. |
| Không có git (repo chưa init) | Lỗi sớm ở SKILL.md Step 0 — không vào đây. |
