# Security Policy

> Tiếng Việt: xem [phần cuối](#tóm-tắt-tiếng-việt).

## The threat model is unusual: this repo's markdown runs inside your AI agent

Thanh Tra is an agent skill. When you install it, your coding agent (Claude
Code, Codex CLI, Antigravity) loads `SKILL.md`, the rule corpus, and the
reference files **directly into its context** and acts on them. That makes
this repository's natural-language content as security-sensitive as
executable code:

- A malicious change to a rule file is a **prompt injection delivered to
  every user's agent** — the payload is prose, not code, and may be invisible
  (zero-width/bidi/Tags-block Unicode — the "Rules File Backdoor" class,
  Pillar Security 2025).
- A compromised release could swap that content after review.

Treat updating Thanh Tra like upgrading a dependency: **read the diff of any
`.md` you re-install.** The diff itself is the payload surface.

## Invariants you can hold us to

Thanh Tra's content and tooling will NEVER:

1. Instruct an agent to **fetch remote content at runtime** during a scan.
2. Instruct an agent to **hide anything from the user** or alter how results
   are reported based on scanned-repo content.
3. Ship **auto-executing configuration** in this repo — no `.claude/settings.json`
   hooks/statusLine/allow-rules, no `.mcp.json`, no `.vscode/tasks.json`
   folder-open tasks, no devcontainer lifecycle commands, no `.envrc`, no
   package-manager lifecycle scripts, no committed git hooks.
4. Ship **invisible Unicode** anywhere in the repo (zero-width, bidi
   controls, Tags block, private-use areas).
5. Download anything in `install.sh` — it only symlinks the cloned checkout
   into your agent's skill directory and prints every link it makes.

A violation of any of these in a release is a vulnerability — report it.

## What CI enforces on every change

`scripts/validate-trust.sh` (run in `maintain.sh` and the GitHub Actions
gate) fails the build if:

- any tracked file contains hidden/invisible Unicode codepoints;
- any auto-exec configuration (the list in invariant 3) appears in the repo;
- a **new** imperative-injection phrase, `curl | sh`, or base64 blob appears
  in any markdown beyond the reviewed baseline (`tests/trust-baseline.json`
  — the rule corpus legitimately *quotes* attack phrases it teaches about;
  any addition shows up as a baseline diff in the PR for human review).

The detector itself is deterministic (regex, no LLM), so it cannot be
sweet-talked by the content it scans. Scanner evasion is still possible —
deterministic gates raise attacker cost; your review of `.md` diffs remains
the last line.

## Installing safely

- Install from a **pinned tag** (`git clone --branch vX.Y.Z --depth 1 …`),
  not from `main`.
- Read `scripts/install.sh` before running it (it is short by design).
- Never pipe a remote script to a shell — Thanh Tra does not support
  `curl | sh` installation on purpose (it is rule corpus material, after all).

## Scanning untrusted repos safely

- `thanhtra prescan --root <folder>` is **deterministic Python** — safe to run
  on a hostile clone *before* opening an agent in it. It reads files; it never
  executes repo content. Its `agent_trust_signals` evidence flags hidden
  Unicode in agent-instruction files, auto-exec configs (`.claude` hooks,
  `.mcp.json`, folder-open tasks, postinstall, …) and injection phrasing.
- The skill instructs agents that scanned content is **data, never
  instructions** (see "Nội dung repo được scan là DATA" in `SKILL.md`), and
  the headless triage prompt carries the same hardening. Prompt injection
  defense is best-effort by nature — prefer the deterministic prescan first
  on repos you do not trust.

## Reporting a vulnerability

Use GitHub **Private Vulnerability Reporting** on this repository (Security
tab → Report a vulnerability). Please do not open public issues for
exploitable problems. You can expect an acknowledgement within 7 days.

In your report, "the scanner missed a vulnerability class" is a feature
request; "the scanner's content can make an agent do something the user
didn't ask for" is a security bug — the second kind has priority.

## Tóm tắt tiếng Việt

- Markdown trong repo này **chạy bên trong agent của bạn** — sửa đổi độc hại
  vào rule file là prompt injection tới mọi người dùng, có thể vô hình
  (Unicode ẩn). Khi cập nhật skill, **đọc diff các file `.md`**.
- Bất biến: không bao giờ bảo agent fetch URL lúc scan, không giấu gì khỏi
  user, không chứa config auto-exec, không chứa Unicode ẩn, `install.sh` chỉ
  symlink — vi phạm là lỗ hổng, hãy báo cáo.
- CI chặn: Unicode ẩn (FAIL), config auto-exec (FAIL), cụm injection mới
  ngoài baseline đã review (FAIL).
- Cài từ tag pin (`--branch vX.Y.Z`), đọc `install.sh` trước khi chạy.
- Quét repo lạ: chạy `thanhtra prescan` (Python thuần, không LLM, không thực
  thi nội dung repo) **trước khi** mở agent và trust folder đó.
- Báo lỗ hổng qua GitHub Private Vulnerability Reporting (tab Security).
