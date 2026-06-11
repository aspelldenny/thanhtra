# Thanh Tra — Backlog

Design context for not-yet-built work. The one-line roadmap lives in `README.md`;
this file keeps the *why* and the decisions so they survive across sessions.

## v1.0 — SARIF output + GitHub Action (CI gate)

Goal: let Thanh Tra run as an automated gate in CI, not just interactively.

Two separable parts — don't conflate them:

1. **`thanhtra scan --sarif`** (Thanh Tra's job — build once, everyone reuses).
   - Emit SARIF 2.1.0 JSON so findings show up natively in GitHub's Security tab
     and as inline annotations on pull requests.
   - Maps the **triage** findings (not raw hotspots) → SARIF `results[]`:
     `rule_id` → `ruleId`, `file`/`line` → `physicalLocation`, `severity` → SARIF
     `level` (CRITICAL/HIGH→error, MEDIUM→warning, LOW→note), `reasoning` →
     `message`. The 22 rules → SARIF `rules[]` (tool driver metadata).
   - Prerequisite: **LLM triage** — DONE (v0.8 anthropic, v0.9 openai). CI needs a
     headless verdict, and that now exists. This is why triage was sequenced first.

2. **Example GitHub Action workflow** (a template users copy — they own it).
   - A `.github/workflows/*.yml` snippet: install Thanh Tra → `scan --sarif` →
     upload via `github/codeql-action/upload-sarif`.
   - **When it runs is the user's call** (per push / per PR / nightly) and **the CI
     minutes are the user's quota** — Thanh Tra only ships the template, doesn't
     mandate cadence. (Decision: deferred to the maintainer because of GitHub
     quota cost.)

## Paused — reopen on real need

- **Ruby / Java overlays.** Skipped intentionally: not worth the complexity for the
  maintainer's stack (uses Claude Code + Codex; codes Rust, not much Ruby/Java).
  Reopen if a real Ruby/Java project needs scanning. Rust overlay shipped (v0.10).
- **More triage providers** (native Gemini, etc.). The `openai`-compatible adapter
  already reaches OpenAI + OpenRouter + Groq + local servers via `--triage-base-url`,
  which covers the realistic need. Add a native provider only if a target API can't
  speak the OpenAI shape.

## Done (for context)

- v0.6 CLI-first deterministic evidence · v0.7 rule #22 PROMPT-INJECTION + inspector
  header · v0.8 LLM triage (Claude) · v0.9 openai-compatible triage provider ·
  v0.10 Rust overlay.
