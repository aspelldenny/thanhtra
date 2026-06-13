#!/usr/bin/env python3
"""Score Thanh Tra's deterministic pre-scan against an EXTERNAL labelled corpus.

Why this exists: fixtures we author ourselves are circular — the same hands (and
agent) write both the rule and the fixture, so passing proves only internal
consistency. An external corpus with independent ground truth (here: Bandit's
``examples/``, each file a known vulnerability class) measures something we
cannot fake: RECALL — of the vulnerabilities that are really there, how many
does the deterministic net surface, and with the right rule?

What this measures (and does NOT):
- It scores the DETERMINISTIC pre-scan layer (``hotspots_by_rule`` +
  ``secret_hits_masked``) — no LLM, fully reproducible. Hotspots are a
  high-recall NET, not findings, so PRECISION at this layer is intentionally
  low (the LLM triage is what filters). We therefore report recall as the
  headline number and treat net breadth as informational, not a failure.
- Ground truth is the intersection of {Bandit example classes} and {Thanh Tra's
  24 rules}. Bandit checks with no Thanh Tra equivalent (XXE, weak TLS, cleartext
  protocols, ...) are OUT OF SCOPE and excluded from the denominator — we do not
  penalise the tool for a class it deliberately does not cover.

Usage: integration_score.py <evidence.json>
"""

from __future__ import annotations

import json
import sys

# Rubric: Bandit example file -> the Thanh Tra rule that SHOULD fire on it.
# Defined from Bandit's documented purpose (independent ground truth), NOT from
# what Thanh Tra happens to catch — misses are meant to show up.
RUBRIC: dict[str, str] = {
    # SQL injection
    "sql_statements.py": "SQL-INJECTION",
    "sql_multiline_statements.py": "SQL-INJECTION",
    "django_sql_injection_raw.py": "SQL-INJECTION",
    "django_sql_injection_extra.py": "SQL-INJECTION",
    # Command / process injection
    "subprocess_shell.py": "COMMAND-INJECTION",
    "os_system.py": "COMMAND-INJECTION",
    "os-popen.py": "COMMAND-INJECTION",
    "os-exec.py": "COMMAND-INJECTION",
    "os-spawn.py": "COMMAND-INJECTION",
    "popen_wrappers.py": "COMMAND-INJECTION",
    "paramiko_injection.py": "COMMAND-INJECTION",
    # Insecure deserialization
    "yaml_load.py": "INSECURE-DESERIALIZATION",
    "pickle_deserialize.py": "INSECURE-DESERIALIZATION",
    "dill.py": "INSECURE-DESERIALIZATION",
    "marshal_deserialize.py": "INSECURE-DESERIALIZATION",
    "jsonpickle.py": "INSECURE-DESERIALIZATION",
    "pandas_read_pickle.py": "INSECURE-DESERIALIZATION",
    "shelve_open.py": "INSECURE-DESERIALIZATION",
    # Weak password hashing
    "crypto-md5.py": "WEAK-PASSWORD-HASHING",
    "hashlib_new_insecure_functions.py": "WEAK-PASSWORD-HASHING",
    # Verbose error / debug
    "flask_debug.py": "VERBOSE-ERROR-DEBUG-MODE",
    # Insecure randomness (Thanh Tra rule 24)
    "random_module.py": "INSECURE-RANDOMNESS",
    # Exception mishandling / fail-open (Thanh Tra rule 23)
    "try_except_pass.py": "EXCEPTION-MISHANDLING",
    "try_except_continue.py": "EXCEPTION-MISHANDLING",
    # Hardcoded secret (detected via secret_hits_masked, not hotspots)
    "hardcoded-passwords.py": "HARDCODED-SECRET",
}

# Bandit's globally issue-free file — nothing should fire here. (Note: files
# like mark_safe_secure.py are clean only w.r.t. their specific check, not
# globally, so they are NOT valid precision oracles — a lesson from this corpus.)
CLEAN_FILES = ["okay.py"]


def files_for_rule(evidence: dict, rule: str) -> set[str]:
    if rule == "HARDCODED-SECRET":
        return {s["path"] for s in evidence.get("secret_hits_masked", [])}
    return {h["path"] for h in evidence.get("hotspots_by_rule", {}).get(rule, [])}


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: integration_score.py <evidence.json>", file=sys.stderr)
        return 2
    evidence = json.load(open(sys.argv[1], encoding="utf-8"))

    # Pre-compute, per rule, which files Thanh Tra flagged.
    flagged = {rule: files_for_rule(evidence, rule) for rule in set(RUBRIC.values())}

    # Recall, grouped by rule.
    by_rule: dict[str, list[tuple[str, bool]]] = {}
    for fname, rule in sorted(RUBRIC.items()):
        caught = fname in flagged[rule]
        by_rule.setdefault(rule, []).append((fname, caught))

    print("Thanh Tra vs Bandit examples — deterministic pre-scan recall")
    print("=" * 64)
    total = caught_total = 0
    missed: list[str] = []
    for rule in sorted(by_rule):
        rows = by_rule[rule]
        c = sum(1 for _, ok in rows if ok)
        total += len(rows)
        caught_total += c
        print(f"\n{rule}  ({c}/{len(rows)})")
        for fname, ok in rows:
            print(f"  [{'x' if ok else ' '}] {fname}")
            if not ok:
                missed.append(f"{fname} -> {rule}")

    recall = (caught_total / total * 100) if total else 0.0
    print("\n" + "=" * 64)
    print(f"RECALL (in-scope): {caught_total}/{total} = {recall:.0f}%")

    # Precision spot-check on Bandit's clean files.
    print("\nClean-file check (should fire nothing):")
    clean_ok = True
    hbr_all = evidence.get("hotspots_by_rule", {})
    for fname in CLEAN_FILES:
        fired = sorted(rule for rule, hits in hbr_all.items()
                       if any(h["path"] == fname for h in hits))
        if fired:
            clean_ok = False
            print(f"  [!] {fname} fired: {', '.join(fired)}")
        else:
            print(f"  [ok] {fname} clean")

    if missed:
        print("\nMisses to investigate:")
        for m in missed:
            print(f"  - {m}")

    # Informational: net breadth (why precision is a triage-layer concern).
    hbr = evidence.get("hotspots_by_rule", {})
    broad = sorted(((rule, len({h["path"] for h in hits})) for rule, hits in hbr.items()),
                   key=lambda x: -x[1])[:3]
    print("\nNet breadth (informational — hotspots are a net, triage filters):")
    for rule, n in broad:
        print(f"  {rule}: flagged {n} files")

    # Exit non-zero only if a clean file regressed; recall is reported, not gated
    # (raise a --min-recall gate later once a baseline is agreed).
    return 0 if clean_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
