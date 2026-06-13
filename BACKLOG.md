# Thanh Tra — Backlog

Design context for not-yet-built work. The one-line roadmap lives in `README.md`;
this file keeps the *why* and the decisions so they survive across sessions.

## Rule-corpus coverage — two update axes (OWASP review 2026-06-12)

Checked the 22-rule corpus against current OWASP standards so future sessions
don't re-derive this. Standing principle: rules are **CWE-classes, not CVE
signatures** — SQL-injection is still SQL-injection next year, so the corpus
does NOT need routine churn. Live CVE freshness is delegated to
`npm/pip/cargo audit` (rule OUTDATED-DEPENDENCY), whose DBs self-update. Update
the corpus only on the events below.

**Reference versions (latest as of 2026-06-12 — don't re-look-up):**
- OWASP Top 10:**2025** for web apps — announced 11/2025, *final 01/2026*. This
  IS the newest web edition; next is ~2028–2029 (3–4yr cadence). No "2026" web
  edition exists. https://owasp.org/Top10/2025/
- OWASP Top 10 for **Agentic Applications 2026** (ASI01–ASI10) — released
  12/2025, the agent-era framework that matters most for this repo (Thanh Tra
  is both a scanner AND an agent skill).
  https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/

### Axis 1 — Web rules (the 22-rule corpus)

Mapping to OWASP Top 10:2025 is good: A01 (BROKEN-ACCESS-CONTROL/IDOR/CSRF/
PATH-TRAVERSAL/SSRF — note 2025 folded SSRF into A01), A02, A03 supply-chain
(SLOPSQUATTING/OUTDATED-DEPENDENCY — we lead OWASP here), A04, A05, A06, A07
(BRUTE-FORCE, thin), A08. Two genuine gaps + one easy win:

- **[rule 23 — SHIPPED v1.3] EXCEPTION-MISHANDLING / fail-open** — OWASP 2025
  **A10** "Mishandling of Exceptional Conditions" (CWE-703/755). Generic rule +
  prescan hotspots (broad/bare catch discriminates from specific `except X:`) +
  fixtures. Per-language catch-idiom overlays still deferred — add on demand
  when a real project's idiom is missed (the proven Rust/Swift/Shell cadence).
- **[rule 24 — SHIPPED v1.3] INSECURE-RANDOMNESS** — `Math.random()`/`rand()`/
  `mt_rand()` for tokens/OTP/session IDs instead of a CSPRNG (CWE-330, under
  A04). Generic rule + prescan hotspots (flags weak PRNG, not `crypto`/`secrets`)
  + fixtures.
- **A09 Security Logging & Alerting Failures: DEFER** — static scan can't
  judge "is logging sufficient"; false-positive prone. Skip unless a real need.
- Not now (add as overlay only when a real project hits them): SSTI as a
  first-class generic rule (currently only in the Python overlay), XXE,
  GraphQL-specific. Don't inflate the corpus on theory.

### Axis 2 — Agentic security (NEW axis, the repo's own frontier)

The v1.2 trust layer already covers ~half of OWASP Agentic 2026 **by
instinct** — it just isn't labelled with ASI codes, so users can't see what
we cover. Mapping found:

| ASI 2026 | What Thanh Tra already has |
|---|---|
| ASI01 Agent Goal Hijack | "scanned content is DATA not instructions" guardrail + injection-marker |
| ASI04 Agentic Supply Chain Compromise | `agent_trust_signals` + SECURITY.md + CI trust gate |
| ASI05 Unexpected Code Execution | auto-exec detector (hooks / .mcp.json / postinstall / folderOpen…) |
| ASI06 Memory & Context Poisoning | hidden-unicode detector (Rules File Backdoor class) |
| ASI09 Human-Agent Trust Exploitation | the whole "scan before you trust the folder" flow |

- **[task A — DONE v1.3] Label the coverage** — `agent_trust_signals` signal
  types now carry their ASI codes in `trust.py` docstrings + a mapping table in
  SECURITY.md ("What we cover in OWASP Agentic 2026 terms"): injection-marker→
  ASI01, auto-exec→ASI05, hidden-unicode→ASI06, the whole stream+CI gate→ASI04,
  prescan-before-trust→ASI09.
- **[task B — DONE v1.3] Survey the other 5 ASI.** Verdict: a *static, pre-LLM,
  repo-level* scanner already covers essentially all of OWASP Agentic 2026 that
  it CAN cover (ASI01/04/05/06/09). The remaining five are runtime/behavioral —
  don't force-fit. Per-item:
  - **ASI02 Tool Misuse — PARTIAL, one candidate signal.** Static angle: grade
    the *scope* of agent tool grants, not just their presence. Today `auto-exec`
    flags that a `.mcp.json` / `permissions.allow` exists; a refinement could
    flag *over-broad* grants (a `.mcp.json` server exposing shell/filesystem, an
    `allow` list with `Bash(*)`/wildcards). Low priority, additive to the trust
    layer — build when a real over-permissive agent repo shows up.
  - **ASI03 Identity & Privilege Abuse — OUT (runtime).** Excessive privilege /
    credential reuse is a runtime identity property; the only static slice is
    hardcoded agent credentials, already caught by HARDCODED-SECRET.
  - **ASI07 Insecure Inter-Agent Comms — OUT / DEFER.** No stable static
    signature; revisit only when a real multi-agent (A2A) repo needs it.
  - **ASI08 Cascading Failures — OUT.** An architecture/resilience property a
    static scan cannot judge.
  - **ASI10 Rogue Agents — OUT (runtime/behavioral).** Detection is environment
    monitoring; the repo-level analog (a malicious agent-instruction file) is
    already ASI06/ASI04 in the trust layer.

### Update cadence (when to revisit this section)

1. New OWASP web edition lands (~2028–2029) → re-map the corpus.
2. AI-era frameworks shift (OWASP GenAI/Agentic move fast — watch for a 2027
   ASI revision) → this is the fastest-moving axis and where the repo leads.
3. A real project needs a stack/class not covered → add overlay/rule on demand
   (the proven cadence: Rust/Swift/Shell all came from real scans).

Adding a rule is ~one session: one markdown file + fixtures + `sync-skills.sh`
+ sync the rule lists in `thanhtra/core/triage.py` and `sarif.py`.

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

## Validation philosophy — benchmarks are a floor, not the mission metric (2026-06-13)

Hard-won during the v1.3.x integration-test work. Persist this so a future
session doesn't burn effort optimising the wrong axis.

- **The mission is vibe-code security:** catch what *AI assistants actually
  generate wrong*, for users who are not security experts. NOT "be a complete
  generic SAST."
- **External benchmarks (Bandit examples, OWASP NodeGoat) are a REGRESSION
  FLOOR, not the target distribution.** They are hand-written OWASP teaching
  corpora, not AI-generated code. `scripts/validate-integration.sh` (Bandit,
  deterministic recall 56% floor) is cheap insurance that the engine still
  detects known classes — keep it, but **do NOT optimise toward it**. A high
  benchmark score = good generic SAST, which is a *different axis* from the
  mission.
- **Rejected: a CODE-INJECTION rule (#25).** NodeGoat's `eval(req.body)` made it
  look like a gap (both a hand-written answer key and the live skill force-fit
  it — to COMMAND-INJECTION and INSECURE-DESERIALIZATION respectively). But
  `eval(userInput)` is **not AI-typical** — modern assistants are trained to
  avoid `eval`; it was a benchmark artifact. Adding it would be benchmark-driven
  drift. Reaffirms the standing rule: **add a rule only when it's AI-typical OR
  a real project hits it** (the proven Rust/Swift/Shell cadence), never because
  a teaching corpus contains it.
- **Mission-true validation = run on REAL AI-generated / real-world code**, not
  teaching apps. On real repos the measurable that matters is **precision /
  false-positive rate** (does it cry wolf on a non-expert's real code?) — the
  one thing all-vulnerable benchmarks *cannot* measure. Recall on real repos has
  no ground truth (the maintainer's own blind-spot insight), so don't chase a
  recall number there.

### LARGE-mode routing: wording is stricter than reality (note, low priority)

The size router trips LARGE on **file count** (>20 main-lang / >30 total), but a
capable model reasons about **LOC / context fit**. On small-LOC repos that cross
the file-count threshold (Bandit 765 LOC, NodeGoat ~2.2k LOC) the model
correctly reads inline (better: full cross-file context, no fragmentation) — and
on genuinely large repos it *does* spawn sub-agents (maintainer confirmed in the
field). So delegation works; the only friction is that `SKILL.md` says "hard
rule — KHÔNG tự hạ mode" while the model sensibly downgrades. Consider relaxing
the wording to "downgrade allowed when you full-read every security-relevant
file and state coverage" instead of an absolute ban the model rationalises
around. Not urgent — behaviour is already good.

## Rule-evolution governance — resist building a prison (2026-06-13)

The single most important principle for evolving this tool. Read before adding
or tightening ANY rule.

**Thanh Tra's role: a third-party periodic auditor, NOT the in-house guardian.**
It scans every 1–2 weeks and produces a signal. It is the smoke detector, not
the fire brigade. There is always a *second line of defence*: the developer /
in-house agent / architect who knows the codebase and triages the report with
full context. Therefore:

- **Blind spots are acceptable.** The second line covers what Thanh Tra misses.
  Do NOT chase 100% recall or a rule for every CWE — that is not this tool's job.
- **Optimise SIGNAL over COMPLETENESS.** Be trustworthy (high precision, low
  noise, catch the big obvious things — the P0 secret, the real XSS) so people
  *act* on the report. A tool that floods false positives gets ignored; a tool
  that misses an edge case is fine because the second line exists.

**More rules → a prison.** Thanh Tra is reasoning-first: rules are a *lens for
the model's intelligence*, not a rigid checklist. The model already reasons
about context (in real runs it independently spotted `debug=True` is under
`if __name__=="__main__"`, that Jinja autoescape doesn't cover JS-context, that
an L3 `exec()` is safe). Encoding those as case-law rules:
- duplicates what the model already does (waste);
- is brittle (the next variation — a different guard, a different idiom —
  slips past the hard-coded condition);
- trains the model to pattern-match the exact condition instead of reasoning
  about the principle — i.e. it makes the model *dumber*, and results get worse.

**The bar to change a rule (the middle way — not too strict, not too loose):**
1. The issue **recurs across MULTIPLE real repos** — never act on n=1.
2. The fix is an **intent clarification** (sharpen the principle, ≤1 line —
   e.g. "WEAK-PASSWORD-HASHING is about the *algorithm* md5/sha1/plaintext, not
   password policy"), **NOT a situational exception**. Clarifying intent sharpens
   the model's reasoning; adding exceptions adds bars to the cage.

**Precedent (rejected tunes, recorded so the rationale persists):**
- *Down-rate `debug=True` under `__main__`* → REJECTED. Textbook prison: the
  model already reasons it; a HIGH-vs-MEDIUM judgement call is not worth a rule;
  brittle to the next guard idiom.
- *Tighten WEAK-PASSWORD-HASHING so it stops tagging "empty password accepted"*
  → DEFERRED. Seen once (n=1) on a real repo (the hashing was correct Werkzeug
  pbkdf2; the model mis-tagged a password-policy issue). Watch for recurrence;
  if it repeats, a one-line intent clarification — not an exception.

The disease to avoid is "saw a false positive → change a rule." ~24 rules
covering the AI-typical classes is *enough*; the model's reasoning + the second
line do the rest.

## Model & vendor variance — cross-check, never trust one report (2026-06-13)

Operational discipline for USING Thanh Tra (not a tool change). Recall is
reasoning-dependent, so it varies by model and by vendor.

**Empirical proof (same repo `tarot`, same skill, same prescan evidence):**
- **Opus 4.8** → verdict PASS, 0 HIGH.
- **Sonnet 4.6** → found a real HIGH that Opus missed: `auth/lite/route.ts`
  rate-limits only the new-account branch; the existing-lite-user refresh path
  returns a fresh session token *before* the limit → unlimited token minting for
  a known lite email. **Verified in code** (rate-limit at line ~132 sits after
  the `if (existing) { … return }` block at ~99–127).

So: **a single model's PASS ≠ clean code** — it means "this model, this run,
found nothing more." (We initially over-praised the Opus PASS as proof the repo
was clean; it wasn't — Opus just didn't find it.)

**Precision/recall trades off between models, neither dominates:** Sonnet had
higher recall (caught the HIGH + more) but lower precision (its sub-agents
over-rated PROMPT-INJECTION → needed downgrade; several "new" findings were
correctness/hygiene, not security). Opus had higher precision, lower recall.

**Go further than same-vendor — cross-VENDOR matters most.** Models differ by
training data, and each training run differs; OpenAI (GPT) and Anthropic
(Claude) diverge MORE than two Claude models do, so cross-vendor checking gives
the most diverse blind-spot coverage. This is exactly why Codex (GPT) plugin
support (the v1.x Codex fix) is worth having — it enables a genuinely
out-of-Anthropic second opinion, not just Opus-vs-Sonnet.

**The rule:** treat any one report as a single opinion. For important
checkpoints (pre-release, a security gate decision), run **≥2 models, ideally
≥2 vendors** (Claude + GPT), union the findings, then triage. Do NOT trust one
report. This is inherent to reasoning-based scanning — not a bug to "fix" in the
tool (no prison); it's how to operate the third-party auditor well.

**Refinement — higher finding-count ≠ better (media-rating, same day).** Re-run
with Sonnet 4.6 produced 3 CRITICAL / 22 HIGH vs Opus 4.8's 1 / 9 — but verifying
in code showed most of the delta was **severity inflation + over-calls**, not 13
real new HIGHs: the same `${POSTGRES_PASSWORD:-changeme}` compose default rated
MEDIUM by Opus → CRITICAL by Sonnet; a letterboxd fetch with a **hardcoded host**
(only the path varies) labelled SSRF (it isn't); a `dev.sh` debug flag rated HIGH
(it's a dev script). Sonnet did catch some real things Opus missed (an avatar
upload with no type/magic check), so it's higher recall AND higher noise — not
"better." Lesson: when models disagree, **do NOT blind-union — triage severity**
(the in-house owner is ground truth); never read "the model that returned more
findings" as the more accurate one.

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
