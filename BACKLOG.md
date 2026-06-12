# Thanh Tra — Backlog

Design context for not-yet-built work. The one-line roadmap lives in `README.md`;
this file keeps the *why* and the decisions so they survive across sessions.

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
- **v1.0 SARIF + GitHub Action (CI gate)** — `scan --sarif` emits SARIF 2.1.0 from
  the *triage* findings (not raw hotspots): triage-dismissed false positives are
  excluded from `results[]` (GitHub would open alerts for them) and counted in
  `run.properties.dismissed_false_positives`; triage failure under `--sarif` exits 1
  so the gate never silently passes with an empty (= all-clear) log. The 22 rules →
  `rules[]` with `security-severity` (9.1/7.5) for GitHub's severity buckets.
  Action template at `examples/github-actions/thanhtra.yml` — cadence and CI
  minutes stay the user's call, per the original decision. Regression gate:
  `scripts/validate-sarif.py` (wired into `maintain.sh`).
- **v1.1 external SAST backend** (reopen trigger "when v1.0 SARIF lands" fired same
  day) — `thanhtra/core/sast.py`: `--semgrep` runs semgrep when installed
  (best-effort like the audit parsers; default `p/default` + `--metrics=off`
  because `auto` requires metrics on), `--sast-sarif` ingests any engine's SARIF.
  Normalized `sast_findings` (suppressed results skipped, capped at `--max-sast`
  with the dropped count recorded) feed the same L1–L4 triage as grep hotspots;
  the triage prompt explicitly says not to trust external severity. Gate:
  `scripts/validate-sast.py`.
- **v1.2 trust defense layer** (pre-open-source requirement). Research-grounded
  (3 parallel briefs, 2026-06-12) — load-bearing facts: (a) "Rules File Backdoor"
  (Pillar 2025) hides instructions in agent rules files via invisible Unicode
  (Tags U+E0000–E007F, zero-width, bidi); vendors ruled it *user responsibility*,
  so the ecosystem won't catch it for us. (b) In Claude Code the trust click arms
  project hooks/statusLine/allow-rules with no per-item consent (`.mcp.json` is
  the lone per-server prompt); `npm install` is the highest-leverage non-AI
  trigger. (c) Trail of Bits bypassed every LLM/skill scanner — so the gate must
  be deterministic (regex can't be sweet-talked): hidden Unicode + auto-exec
  configs hard-FAIL; injection phrases diff against a reviewed baseline
  (`tests/trust-baseline.json`) because the rule corpus legitimately quotes
  attack phrasing. Shipped: `thanhtra/core/trust.py` detector (also feeds
  `agent_trust_signals` into prescan evidence for scanning *other* repos before
  trusting their folder), skill + triage anti-injection guardrails, SECURITY.md
  invariants, `.github/workflows/gate.yml` (read-only token, sync-drift check),
  `scripts/validate-trust.py` self-test + self-scan.
