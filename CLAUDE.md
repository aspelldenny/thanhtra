# Thanh Tra — agent guide

Security scanner for AI-generated code, shipped in two forms from this one repo:

1. **Agent skill** (`skills/`) — loaded by Claude Code / Codex CLI / Antigravity; invoked as `/thanhtra`. The markdown in `skills/` IS the product: rules and instructions executed inside users' agents.
2. **CLI** (`bin/thanhtra`) — deterministic Python, **stdlib only, zero dependencies, Python 3.10+**. Works straight from a clone, no install step.

## Common commands

```bash
./bin/thanhtra scan <repo> --json --no-audit    # mechanical evidence (safe on untrusted repos)
./bin/thanhtra scan <repo> --triage             # + LLM verdict (needs ANTHROPIC_API_KEY)
./bin/thanhtra scan <repo> --sarif --output o.sarif   # CI gate output (implies --triage)
./scripts/maintain.sh                           # full validation gate — run before every commit
```

## Repo map

- `skills/thanhtra/` — **canonical** skill (rules, references, workflows). `skills/codex/` and `skills/antigravity/` are generated copies: never edit them directly; edit canonical then run `./scripts/sync-skills.sh`. CI fails on drift.
- `thanhtra/` — Python package (prescan / triage / sarif / sast / trust).
- `scripts/validate-*.sh` — per-area regression gates, all wired into `maintain.sh`.
- `BACKLOG.md` — design context and decisions; `SECURITY.md` — threat model.

## Rules for working on this repo

- **The `.md` files in `skills/` run inside users' agents.** A diff to a rule file is security-sensitive content, not just docs — see `SECURITY.md`. Review such diffs as if they were executable code.
- **Trust gate** (`scripts/validate-trust.sh`, part of `maintain.sh` and CI): hidden/invisible Unicode or auto-executing configs anywhere in the repo are a hard FAIL. New imperative-injection phrasing in markdown fails until a human reviews it and runs `scripts/validate-trust.sh --rebaseline` — and rebaseline reads `git ls-files`, so **`git add` new files first**, then rebaseline.
- Never commit literal invisible Unicode characters, even in tests — write them as escape sequences in code/string form (backslash-u200b, `\U000E0041`, …). This very rule has been tripped three times while building the gate; it catches everyone.
- Severity caps, the 22 rule IDs, and the L1–L4 trust model are defined in `skills/thanhtra/rules/` and mirrored in `thanhtra/core/triage.py` — keep them in sync when adding a rule.
- Reports and skill output are bilingual (vi default, `lang=en`); CLI/JSON stays English.
