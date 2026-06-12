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

## Future axis — non-reasoning analysis layer (DEFER)

Context: every layer in the maintainer's current security posture — Thanh Tra,
the two bounded reviewer roles (boundary/advisory), and the periodic Codex pass —
is **LLM reasoning**. Two frontier vendors (Claude + Codex) give two independent
blind-spot profiles, which is good lens-diversity for a solo. But the real ceiling
isn't "only two models" — it's that *all* layers are reasoning-based. Thanh Tra's
pre-scan is grep-pattern, which *guides* the LLM but doesn't raise the ceiling.

The axis that genuinely escapes the reasoning ceiling is **analysis that doesn't
reason**, because it catches a different *class* of bug:

- **Sound static analysis with real dataflow** (CodeQL / Semgrep) — exhaustive
  taint tracking, not "read and understand." Natural reopen path: wire a real SAST
  engine as a *pre-scan backend* feeding hotspots into the existing LLM triage —
  augment, don't replace, the L1–L4 triage layer.
- **Fuzzing / DAST runtime** — throw malformed input at the running app; finds what
  static reading can't.
- **Deterministic CVE / secret feeds** — mechanical, no model (pre-scan already does
  a thin version of this via `pnpm/npm/pip/cargo audit`).

**Decision: DEFER — but it's two rungs, not one.**

- **CodeQL / fuzzing / DAST: defer outright.** Building that machinery now is
  solving a scale problem not yet had — exactly the AI-completeness bias the host
  guards against. (This is the second independent session to land on defer for
  CodeQL — an earlier one already judged it too heavy to rush. Consistent
  conclusion; don't re-litigate without new facts.)
- **Semgrep as an optional pre-scan backend: defer only until v1.0.** With default
  rulesets it weighs about the same as the audit parsers the pre-scan already runs
  (`pip/npm/pnpm/cargo audit` — mechanical, no model, same philosophy). And it
  composes naturally with the v1.0 SARIF work: SARIF is the lingua franca of SAST,
  so once `thanhtra scan --sarif` *emits* SARIF, *accepting* semgrep's SARIF as a
  hotspot source is nearly free by design. Reopen trigger: **when v1.0 SARIF
  lands** — not "when the app has traffic".

Reopen trigger for the heavy rung, made concrete (the old "real value/traffic/
attack surface worth targeting" is already half-true — tarot takes real money via
PayOS): **public signups + real revenue, or before the first external pentest.**

The current kit (mechanical pre-scan + L1–L4 triage + bounded roles + periodic
different-vendor Codex pass) is proportionate. Supporting evidence from the two
2026-06-12 scans (tarot, soulsign-marketing): every finding that mattered was a
*judgment* call (trust-model downgrade, intent inference, accept-risk framing) —
the class SAST can't make — while the class SAST uniquely catches (deep taint
chains) is exactly where those repos are already hardened by multiple review
rounds. The reasoning-x2-vendor ceiling is the *current* limit, not an *urgent*
hole.

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
  v0.10 Rust overlay · v0.11 Swift overlay · v0.12 Shell overlay (motivated by the
  soulsign-marketing scan: 12 shell files scanned with generic rules only; the
  heredoc-splice finding is now a first-class pattern).
