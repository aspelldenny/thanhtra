# Thanh Tra — agent guide

Security scanner for AI-generated code, shipped in two forms from this one repo:

1. **Agent skill** (`skills/`) — loaded by Claude Code / Codex CLI / Antigravity; invoked as `/thanhtra`. The markdown in `skills/` IS the product: rules and instructions executed inside users' agents.
2. **CLI** (`bin/thanhtra`) — deterministic Python, **stdlib only, zero dependencies, Python 3.10+**. Works straight from a clone, no install step.

## Using Thanh Tra to scan code (start here if you just want to run it)

If the user wants to **scan their code** (not modify this repo), there are two ways:

1. **Agent skill** — install once, then invoke inside any project:
   ```bash
   ./scripts/install.sh    # auto-detects Claude Code / Codex / Antigravity, symlinks the skill
   ```
   Then trigger it: `/thanhtra` (Claude Code). On **Codex CLI** it installs as a plugin (`codex plugin add thanhtra@thanhtra-local`) and the skill is model-invoked — just ask *"scan security"* / *"kiểm tra bảo mật"*. On Antigravity, ask *"scan security"*. The agent reads the rules and produces a bilingual report (Vietnamese default, add `lang=en` for English).
2. **CLI** — no install, no API key, pure Python:
   ```bash
   ./bin/thanhtra scan <repo> --json --no-audit
   ```

Full A-to-Z for humans: [README.md](README.md). Everything below this section is for working **on** this repo.

## Common commands

```bash
./bin/thanhtra scan <repo> --json --no-audit    # mechanical evidence (safe on untrusted repos)
./bin/thanhtra scan <repo> --triage             # + LLM verdict (needs ANTHROPIC_API_KEY)
./bin/thanhtra scan <repo> --sarif --output o.sarif   # CI gate output (implies --triage)
./scripts/maintain.sh                           # full validation gate — run before every commit
```

## Repo map

- `skills/thanhtra/` — **canonical** skill (rules, references, workflows). `skills/antigravity/thanhtra/` is a generated copy; `skills/codex/` is a **Codex plugin marketplace** wrapping the generated skill at `plugins/thanhtra/skills/thanhtra/` (manifests `.agents/plugins/marketplace.json` + `plugins/thanhtra/.codex-plugin/plugin.json` are hand-maintained). Never edit the generated skill dirs directly; edit canonical then run `./scripts/sync-skills.sh`. CI fails on drift.
- `thanhtra/` — Python package (prescan / triage / sarif / sast / trust).
- `scripts/validate-*.sh` — per-area regression gates, all wired into `maintain.sh`.
- `BACKLOG.md` — design context and decisions; `SECURITY.md` — threat model.

## Rules for working on this repo

- **The `.md` files in `skills/` run inside users' agents.** A diff to a rule file is security-sensitive content, not just docs — see `SECURITY.md`. Review such diffs as if they were executable code.
- **Trust gate** (`scripts/validate-trust.sh`, part of `maintain.sh` and CI): hidden/invisible Unicode or auto-executing configs anywhere in the repo are a hard FAIL. New imperative-injection phrasing in markdown fails until a human reviews it and runs `scripts/validate-trust.sh --rebaseline` — and rebaseline reads `git ls-files`, so **`git add` new files first**, then rebaseline.
- Never commit literal invisible Unicode characters, even in tests — write them as escape sequences in code/string form (backslash-u200b, `\U000E0041`, …). This very rule has been tripped three times while building the gate; it catches everyone.
- Severity caps, the 24 rule IDs, and the L1–L4 trust model are defined in `skills/thanhtra/rules/` and mirrored in `thanhtra/core/triage.py` — keep them in sync when adding a rule.
- Reports and skill output are bilingual (vi default, `lang=en`); CLI/JSON stays English.
