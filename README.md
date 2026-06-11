<div align="center">

### 🇻🇳 [Đọc bằng Tiếng Việt → README.vi.md](README.vi.md)

</div>

---

# Thanh Tra — Source Code Security Scanner

Thanh Tra is a CLI-first security scanner and multi-platform agent skill that performs in-depth security scans and detects 20+ of the most common security vulnerabilities in your source code. Runs natively on **Claude Code**, **OpenAI Codex CLI**, and **Google Antigravity**.

> Credit: Thanh Tra is built from the MIT-licensed `vbsec` skill shared from the original project by **Bùi Tấn Việt** and **Phan Quốc Hiên**. The upstream rule corpus and platform-skill foundation remain credited in this fork.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Claude Code](https://img.shields.io/badge/Claude%20Code-Skill-blue)](https://docs.claude.com/claude-code)
[![OpenAI Codex](https://img.shields.io/badge/OpenAI%20Codex-Skill-black)](https://developers.openai.com/codex/skills)
[![Google Antigravity](https://img.shields.io/badge/Google%20Antigravity-Skill-orange)](https://antigravity.google/docs/skills)

---

## Introduction

AI-generated code now represents a meaningful share of new commits across the industry. While modern coding assistants excel at producing code that *works*, they routinely ship code with classic security pitfalls: hardcoded secrets, SQL injection, missing access controls, weak password hashing, JWT misuse, and broken CORS configurations. These mistakes rarely surface in functional testing — they surface in incident reports.

Thanh Tra brings production-grade security review into the AI coding loop. It runs as a native agent skill on three platforms — type `/thanhtra` in Claude Code, `$thanhtra` (or `/skills`) in OpenAI Codex CLI, or simply ask Google Antigravity to "scan security" — and receive a structured report covering 20+ categories of vulnerabilities. It also ships a CLI-first deterministic scanner via `bin/thanhtra scan --json`.

Thanh Tra has been exercised against intentionally vulnerable open-source training apps such as OWASP Juice Shop — and identifies findings that line up with the documented vulnerability challenges across SQL injection, NoSQL injection, JWT misuse, broken access control, mass assignment, deserialization RCE, and more.

Generic rules apply to every language. Specialized rule overlays exist for Go, PHP, TypeScript/JavaScript, and Python, covering common frameworks: React, Vue, Angular, Express, NestJS, Next.js, Django, Flask, FastAPI, SQLAlchemy, Sequelize, Prisma, and Mongoose. Additional language overlays are on the roadmap.

## Authors

- **Bùi Tấn Việt** — CEO, [SePay](https://sepay.vn) & [123HOST](https://123host.vn)
- **Phan Quốc Hiên** — CTO, [SePay](https://sepay.vn) & [123HOST](https://123host.vn)

## How it works

Thanh Tra is engineered around a small set of design choices that distinguish it from conventional pattern scanners.

- **Reasoning-first, not pattern counting.** Thanh Tra does not blindly grep for `eval(` or `query(`. Each potential finding is verified by reading the surrounding code, tracing data flow (L1 untrusted user input through L4 trusted system data), and confirming the data reaches a dangerous sink without sanitization. This eliminates the false-positive flood typical of regex-based scanners.

- **Size-aware routing.** Small scans (≤20 main-language files AND ≤30 total) run inline in 30-60 seconds. Larger scans automatically delegate work to sub-agents that run in parallel — one chunk per top-level folder — and aggregate findings centrally. The user experience is identical; only the execution strategy changes.

- **Sub-agent delegation for large repositories.** For repositories with hundreds of files, Thanh Tra spawns up to three parallel sub-agents through Claude Code's general-purpose agent. Each sub-agent scans a chunk of files independently, and findings are dedupe-aggregated by `(file, line, rule_id)`. This keeps wall-clock time bounded even on monorepos.

- **Language overlay system.** When Thanh Tra detects the primary language, it loads language-specific rule files from `rules/languages/<lang>/` that override the generic rules for that language. This catches framework-specific patterns: Mongoose `$where` NoSQL injection, Angular `bypassSecurityTrustHtml`, Sequelize template-literal SQL, JWT algorithm confusion, Gin debug mode in production builds.

- **L1–L4 data flow classification.** Inputs are classified by trust level. A `db.query(\`SELECT ${x}\`)` call is only reported as a finding when `x` originates from L1 (user-controlled input) and reaches the SQL sink without parameterization. Constants, environment variables, and trusted-source data do not generate false positives.

- **One finding, one rule.** A line of code that triggers both IDOR and Race Condition produces two findings — never a comma-separated double tag. This keeps counts honest, reports auditable, and the trailing JSON summary machine-parseable.

- **Bilingual reports.** Vietnamese is the default; English is selected with `lang=en`. The JSON summary at the report tail is always canonical English for CI and tooling consumption.

- **Multi-platform.** One canonical rule set, three platform variants. Claude Code uses parallel sub-agents for large scans; Codex and Antigravity use sequential chunking with identical output. A single `sync-skills.sh` script keeps rule definitions in lock-step across all three.

## Multi-platform support

Thanh Tra ships three variants from a single source of truth:

| Platform | Skill folder | Install target | LARGE mode strategy |
|---|---|---|---|
| Claude Code | `skills/thanhtra/` | `~/.claude/skills/thanhtra` | Parallel sub-agents (3 concurrent) |
| OpenAI Codex CLI | `skills/codex/thanhtra/` | `~/.agents/skills/thanhtra` | Sequential chunking |
| Google Antigravity | `skills/antigravity/thanhtra/` | `~/.gemini/antigravity/skills/thanhtra` | Sequential chunking |

All three share the same 22 rules, language overlays, i18n strings, and output format. Findings are identical; only execution strategy differs. Sequential variants are ~3× slower wall-clock than Claude Code's parallel mode on large repositories, but produce the same JSON summary and the same Markdown report.

Contributors: edit rules in `skills/thanhtra/` (the canonical Claude folder), then run `./scripts/sync-skills.sh` to propagate to the Codex and Antigravity variants. Platform-specific files (`SKILL.md`, `workflows/large-review*.md`) are hand-maintained.

## Installation

Thanh Tra auto-detects every supported platform you have installed and wires up the skill. Run:

```bash
git clone https://github.com/aspelldenny/thanhtra ~/thanhtra
cd ~/thanhtra
./scripts/install.sh         # auto-detect, install for what's present
./scripts/install.sh --all   # force install for all 3 platforms regardless
```

Detection logic:
- **Claude Code** — binary `claude` in PATH
- **OpenAI Codex CLI** — binary `codex` in PATH
- **Google Antigravity** — app at `/Applications/Antigravity.app` (macOS) OR CLI tool `agy` in PATH (installed via Antigravity IDE menu)

Antigravity is an IDE (like VS Code), not a CLI. For a brand-new Antigravity user, the folder `~/.gemini/antigravity/skills/` does not exist by default — the installer creates it for you.

The installer symlinks the appropriate skill folder into each platform's expected location. To update later:

```bash
cd ~/thanhtra && git pull
```

(Symlinks pick up the new version automatically; restart the CLI / IDE if needed.)

**Manual install for a single platform:**

```bash
# Claude Code
ln -sfn ~/thanhtra/skills/thanhtra              ~/.claude/skills/thanhtra

# OpenAI Codex CLI
ln -sfn ~/thanhtra/skills/codex/thanhtra        ~/.agents/skills/thanhtra

# Google Antigravity
ln -sfn ~/thanhtra/skills/antigravity/thanhtra  ~/.gemini/antigravity/skills/thanhtra
```

Verify the install on each platform:

```
Claude Code:   /thanhtra
Codex:         $thanhtra        (or /skills, then pick)
Antigravity:   "scan security cho repo này"  (auto-trigger by description)
```

See [docs/en/installation.md](docs/en/installation.md) for prerequisites, troubleshooting, and update procedures.

## Usage

The default scope is the entire repository. This is a deliberate change from earlier versions and matches how teams typically request a security audit.

```bash
/thanhtra                       # scan entire folder (default)
/thanhtra uncommitted           # only scan uncommitted changes
/thanhtra pr id 42 lang=en      # scan a PR, report in English
/thanhtra commit within 7days   # scan last 7 days of commits
```

**Works without git.** Vibe coders rarely init `git` before pasting AI-generated code into a folder. The default scope (`/thanhtra`) walks the filesystem directly when no `.git/` is present — common build/vendored folders are excluded automatically. Git-specific scopes (`uncommitted`, `staged`, `commit within`, `commit id`, `pr id`) still require a git repository and will print a helpful message asking you to init git or fall back to the default scope.

Reports are saved to `thanhtra-reports/scan-<timestamp>.md` inside the scanned folder for re-reading, sharing with reviewers, and attaching to remediation tickets.

See [docs/en/usage.md](docs/en/usage.md) for all options including `staged`, single-commit scans, and PR scanning via `gh`.

### CLI pre-scan JSON

Thanh Tra ships a phase-1 CLI for deterministic evidence collection. `./scripts/install.sh` symlinks it into `~/.local/bin`, so `thanhtra` is callable from any repo:

```bash
thanhtra scan /path/to/repo --json
thanhtra scan /path/to/repo --json --output /tmp/thanhtra-scan.json
thanhtra scan /path/to/repo --json --no-audit
thanhtra prescan --root . --output .thanhtra-pre-scan.json   # raw evidence, what agent skills consume
thanhtra scan /path/to/repo --json --triage                  # add LLM verdict (needs ANTHROPIC_API_KEY)
```

`scan` emits `schema: "thanhtra-scan/v1"`, a compact summary, and raw `evidence`. `prescan` emits the raw evidence document (`thanhtra-pre-scan/v1`) that agent skills read before LLM reasoning. Both are intentionally mechanical: dependency audit, secret masking, Docker exposure checks, file classification, and hotspot collection — the CLI is the single source of truth; the script bundled inside the skill is only a fallback wrapper for machines without the CLI on PATH.

### Optional LLM triage (headless verdict)

`scan --triage` (or the standalone `thanhtra triage`) reasons over the mechanical evidence with an LLM — removing false positives, mapping findings to rules, and producing a `PASS`/`WARN`/`FAIL` verdict — without opening an agent. This is what makes Thanh Tra usable in CI or a cron job, where no one is around to run the `/thanhtra` skill interactively.

```bash
# Anthropic (default)
export ANTHROPIC_API_KEY=...
thanhtra scan . --json --triage                    # mechanical evidence + verdict in one document
thanhtra prescan --root . | thanhtra triage --evidence -   # triage evidence from stdin

# OpenAI — or any OpenAI-compatible endpoint
export OPENAI_API_KEY=...
thanhtra scan . --triage --triage-provider openai --triage-model gpt-5.1

# OpenRouter / Groq / Together / local Ollama — same adapter, different base URL
thanhtra scan . --triage --triage-provider openai \
  --triage-base-url https://openrouter.ai/api/v1 --triage-model anthropic/claude-opus-4
```

The triage layer is **optional and pluggable**, with two providers:

- **`anthropic`** (default) — Claude Messages API, model `claude-opus-4-8`. Uses the `anthropic` SDK if installed, else a stdlib HTTP call (so the CLI stays zero-install).
- **`openai`** — any OpenAI-compatible `/chat/completions` endpoint. One adapter covers OpenAI, OpenRouter, Groq, Together, DeepSeek, and local servers (Ollama, LM Studio, vLLM) — set `--triage-base-url` (or `THANHTRA_TRIAGE_BASE_URL`) and a `--triage-model`. Key from `OPENAI_API_KEY` (or `THANHTRA_TRIAGE_API_KEY`). It requests strict JSON-schema output and falls back to plain JSON for servers that don't support it.

Select via `--triage-provider` / `THANHTRA_TRIAGE_PROVIDER`. Triage degrades gracefully — without a key, `scan --triage` still emits the full mechanical evidence and notes `triage_error`.

## Vulnerabilities Thanh Tra detects

| # | Rule ID | Severity max | Specialized for |
|---|---|---|---|
| 1 | `HARDCODED-SECRET` | CRITICAL | — |
| 2 | `SQL-INJECTION` | CRITICAL | go, php, typescript |
| 3 | `XSS` | HIGH | typescript |
| 4 | `IDOR` | HIGH | — |
| 5 | `SLOPSQUATTING` | CRITICAL | — |
| 6 | `BRUTE-FORCE` | HIGH | — |
| 7 | `MASS-ASSIGNMENT` | CRITICAL | typescript |
| 8 | `INSECURE-DESERIALIZATION` | CRITICAL | go, php, typescript |
| 9 | `SSRF` | HIGH | go, typescript |
| 10 | `PATH-TRAVERSAL` | HIGH | — |
| 11 | `CSRF` | HIGH | php, typescript |
| 12 | `BROKEN-ACCESS-CONTROL` | CRITICAL | — |
| 13 | `WEAK-PASSWORD-HASHING` | CRITICAL | — |
| 14 | `JWT-NONE-ALGORITHM` | CRITICAL | typescript |
| 15 | `CORS-MISCONFIG` | HIGH | typescript |
| 16 | `UNRESTRICTED-FILE-UPLOAD` | CRITICAL | — |
| 17 | `VERBOSE-ERROR-DEBUG-MODE` | HIGH | go, php, typescript |
| 18 | `MISSING-RATE-LIMIT` | HIGH | — |
| 19 | `RACE-CONDITION` | HIGH | — |
| 20 | `OUTDATED-DEPENDENCY` | HIGH | — |
| 21 | `COMMAND-INJECTION` | CRITICAL | go, php, typescript |

The list currently contains 22 rules and will continue to expand.

## Documentation

- [Installation](docs/en/installation.md)
- [Usage](docs/en/usage.md)
- [Full rule catalog](docs/en/rules.md)
- [Contributing](docs/en/contributing.md)
- [Maintenance](docs/en/maintenance.md)

## Roadmap

- v0.1 — Generic rule set + Go + PHP specialization + bilingual output ✅
- v0.2 — TypeScript/JavaScript specialization (Sequelize/Prisma/Mongoose, React/Vue/Angular, Express/NestJS/Next.js) ✅
- v0.3 — Default scope changed to full-repo, persistent reports, verbose per-finding explanations ✅
- v0.4 — Python specialization (SQLAlchemy/Django ORM SQLi, pickle/yaml deserialization RCE, Werkzeug debugger, FastAPI/Flask/Django CSRF + CORS, PyJWT algorithms, subprocess shell=True) ✅
- v0.5 — Multi-platform support: OpenAI Codex CLI + Google Antigravity (sequential LARGE mode, shared rule set, `install.sh` + `sync-skills.sh`) ✅
- v0.6 — Thanh Tra CLI-first deterministic evidence: `bin/thanhtra scan --json`, dependency audit parsing, audit gaps, file classification ✅
- v0.7 — Rule #22 PROMPT-INJECTION for LLM/agent apps (direct + context-poisoning); report header records the inspector (model identity) for cross-run comparison ✅
- v0.8 — Optional LLM triage: `scan --triage` / `thanhtra triage` reasons over the evidence headless (false-positive removal, rule mapping, PASS/WARN/FAIL verdict) via the Claude API, SDK-or-stdlib ✅
- v0.9 (current) — `openai` triage provider: one OpenAI-compatible adapter covers OpenAI, OpenRouter, Groq, Together, DeepSeek, and local servers (Ollama/LM Studio/vLLM) via `--triage-base-url` ✅
- v1.0+ — Rust overlay; SARIF + GitHub Action (CI gate)

## Disclaimer

Thanh Tra is a reference scanner. It catches common AI-generated code mistakes, but:

- It does NOT replace a professional security audit
- It does NOT guarantee 100% vulnerability coverage
- It does NOT fetch live CVE databases (run `npm audit` / `pip-audit` / `govulncheck` separately for that)

Use Thanh Tra as a **first line of defense**, not as proof of security.

## License & Acknowledgments

Released under the [MIT License](LICENSE).

Built on the security expertise of [SePay](https://sepay.vn) and [123HOST](https://123host.vn) — two Vietnamese fintech and hosting companies that operate production systems under real-world threat conditions.

© 2026 Bùi Tấn Việt & Phan Quốc Hiên.
