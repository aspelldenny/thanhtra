#!/usr/bin/env python3
"""Regression checks for the SARIF 2.1.0 emitter (`thanhtra scan --sarif`)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
THANHTRA_CLI = ROOT / "bin" / "thanhtra"

sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT))

from thanhtra.core.sarif import RULES, to_sarif  # noqa: E402
from thanhtra.core.triage import ALL_RULES, CRITICAL_RULES  # noqa: E402

failures = 0


def check(condition: bool, message: str) -> None:
    global failures
    if condition:
        print(f"OK: {message}")
    else:
        failures += 1
        print(f"FAIL: {message}", file=sys.stderr)


def sample_document() -> dict:
    return {
        "schema": "thanhtra-scan/v1",
        "generated_at": "2026-06-12T00:00:00+00:00",
        "root": "/tmp/fixture",
        "triage": {
            "verdict": "FAIL",
            "summary": "1 critical SQLi, 1 medium, 1 low; 1 dismissed",
            "provider": "anthropic",
            "model": "claude-opus-4-8",
            "findings": [
                {
                    "rule_id": "SQL-INJECTION", "severity": "CRITICAL",
                    "file": "./app/db.py", "line": 42,
                    "title": "Raw f-string query", "reasoning": "L1 request param reaches cursor.execute",
                    "false_positive": False, "confidence": 90,
                },
                {
                    "rule_id": "CORS-MISCONFIG", "severity": "MEDIUM",
                    "file": "server/main.go", "line": 7,
                    "title": "Wildcard origin", "reasoning": "No credentials, internal API",
                    "false_positive": False, "confidence": 70,
                },
                {
                    "rule_id": "VERBOSE-ERROR-DEBUG-MODE", "severity": "LOW",
                    "file": "config.php", "line": 0,
                    "title": "display_errors on", "reasoning": "Dev-only config block",
                    "false_positive": False, "confidence": 60,
                },
                {
                    "rule_id": "HARDCODED-SECRET", "severity": "CRITICAL",
                    "file": "tests/fake_key.py", "line": 3,
                    "title": "Test fixture key", "reasoning": "Clearly a placeholder, L4",
                    "false_positive": True, "confidence": 95,
                },
            ],
        },
    }


def main() -> int:
    log = to_sarif(sample_document())

    check(log["version"] == "2.1.0", "version is 2.1.0")
    check("sarif-schema-2.1.0" in log["$schema"], "$schema points at SARIF 2.1.0")
    check(len(log["runs"]) == 1, "single run")

    run = log["runs"][0]
    driver = run["tool"]["driver"]
    check(driver["name"] == "Thanh Tra", "driver name")
    rules = driver["rules"]
    check(len(rules) == 22, "driver declares all 22 rules")
    check([r["id"] for r in rules] == sorted(ALL_RULES, key=[r[0] for r in RULES].index),
          "rule ids cover the canonical corpus")
    check({r[0] for r in RULES} == set(ALL_RULES), "sarif rule table matches triage ALL_RULES")
    check({r[0] for r in RULES if r[1] == "CRITICAL"} == CRITICAL_RULES,
          "sarif severity_max matches triage CRITICAL_RULES")
    for r in rules:
        check("." not in r["name"] and "-" not in r["name"], f"rule name is an identifier: {r['name']}")
        check(r["helpUri"].endswith(".md"), f"rule helpUri set: {r['id']}")
        check("security-severity" in r["properties"], f"security-severity set: {r['id']}")

    results = run["results"]
    check(len(results) == 3, "false positive excluded from results")
    check(run["properties"]["dismissed_false_positives"] == 1, "dismissed FP counted in run properties")
    check(run["properties"]["verdict"] == "FAIL", "verdict carried in run properties")

    by_rule = {r["ruleId"]: r for r in results}
    check(by_rule["SQL-INJECTION"]["level"] == "error", "CRITICAL maps to error")
    check(by_rule["CORS-MISCONFIG"]["level"] == "warning", "MEDIUM maps to warning")
    check(by_rule["VERBOSE-ERROR-DEBUG-MODE"]["level"] == "note", "LOW maps to note")

    loc = by_rule["SQL-INJECTION"]["locations"][0]["physicalLocation"]
    check(loc["artifactLocation"]["uri"] == "app/db.py", "leading ./ stripped from uri")
    check(loc["region"]["startLine"] == 42, "line carried into region.startLine")
    loc0 = by_rule["VERBOSE-ERROR-DEBUG-MODE"]["locations"][0]["physicalLocation"]
    check(loc0["region"]["startLine"] == 1, "line 0 clamped to 1 (SARIF requires >= 1)")

    for r in results:
        check(r["ruleIndex"] == [x["id"] for x in rules].index(r["ruleId"]),
              f"ruleIndex consistent for {r['ruleId']}")
        check("— " in r["message"]["text"] or r["message"]["text"], f"message non-empty for {r['ruleId']}")

    # Unknown rule id must not crash (forward compat with future rules).
    doc = sample_document()
    doc["triage"]["findings"] = [{
        "rule_id": "FUTURE-RULE", "severity": "HIGH", "file": "x.py", "line": 1,
        "title": "t", "reasoning": "r", "false_positive": False, "confidence": 50,
    }]
    odd = to_sarif(doc)["runs"][0]["results"][0]
    check(odd["ruleId"] == "FUTURE-RULE" and "ruleIndex" not in odd,
          "unknown rule id emitted without ruleIndex")

    # No triage section → hard error, never a silent empty log.
    try:
        to_sarif({"schema": "thanhtra-scan/v1"})
        check(False, "to_sarif rejects document without triage")
    except ValueError:
        check(True, "to_sarif rejects document without triage")

    # CLI smoke: --sarif without any API key must exit 1, not print SARIF.
    env = {k: v for k, v in os.environ.items()
           if k not in {"ANTHROPIC_API_KEY", "OPENAI_API_KEY", "THANHTRA_TRIAGE_API_KEY"}}
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "app.py").write_text("print('hi')\n", encoding="utf-8")
        proc = subprocess.run(
            [sys.executable, str(THANHTRA_CLI), "scan", tmp, "--sarif", "--no-audit"],
            capture_output=True, text=True, env=env,
        )
    check(proc.returncode == 1, "scan --sarif without API key exits 1")
    check("triage" in proc.stderr, "scan --sarif failure explains triage is required")
    check(not proc.stdout.strip(), "scan --sarif failure emits no SARIF on stdout")

    # The sample SARIF must be valid JSON end-to-end.
    json.loads(json.dumps(log))
    check(True, "sarif log is JSON-serializable")

    if failures:
        print(f"\n{failures} check(s) failed", file=sys.stderr)
        return 1
    print("\nAll SARIF checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
