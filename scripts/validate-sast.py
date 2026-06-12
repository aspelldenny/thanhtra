#!/usr/bin/env python3
"""Regression checks for the external SAST ingest (semgrep / --sast-sarif)."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
THANHTRA_CLI = ROOT / "bin" / "thanhtra"

sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT))

from thanhtra.core import sast  # noqa: E402

failures = 0


def check(condition: bool, message: str) -> None:
    global failures
    if condition:
        print(f"OK: {message}")
    else:
        failures += 1
        print(f"FAIL: {message}", file=sys.stderr)


def sample_sarif(root: Path) -> dict:
    return {
        "version": "2.1.0",
        "runs": [{
            "tool": {"driver": {
                "name": "semgrep",
                "rules": [
                    {"id": "python.lang.security.audit.exec-detected",
                     "defaultConfiguration": {"level": "error"}},
                ],
            }},
            "results": [
                {  # level from result
                    "ruleId": "python.flask.security.injection.tainted-sql-string",
                    "level": "error",
                    "message": {"text": "Tainted data flows into SQL string. " + "x" * 400},
                    "locations": [{"physicalLocation": {
                        "artifactLocation": {"uri": f"file://{root}/app/db.py"},
                        "region": {"startLine": 12},
                    }}],
                },
                {  # level falls back to rule defaultConfiguration
                    "ruleId": "python.lang.security.audit.exec-detected",
                    "message": {"text": "exec() detected"},
                    "locations": [{"physicalLocation": {
                        "artifactLocation": {"uri": "./srv/run.py"},
                        "region": {"startLine": 3},
                    }}],
                },
                {  # suppressed result must be skipped
                    "ruleId": "ignored.rule",
                    "level": "warning",
                    "message": {"text": "suppressed"},
                    "suppressions": [{"kind": "inSource"}],
                    "locations": [{"physicalLocation": {
                        "artifactLocation": {"uri": "x.py"},
                        "region": {"startLine": 1},
                    }}],
                },
            ],
        }],
    }


def main() -> int:
    root = Path("/tmp/fixture-root")
    findings = sast.normalize_sarif(sample_sarif(root), source="semgrep", root=root)

    check(len(findings) == 2, "suppressed result skipped, 2 of 3 kept")
    sql, exc = findings
    check(sql["file"] == "app/db.py", "file:// absolute uri made root-relative")
    check(exc["file"] == "srv/run.py", "./ prefix stripped from relative uri")
    check(sql["line"] == 12 and exc["line"] == 3, "startLine carried through")
    check(sql["level"] == "error", "result-level level kept")
    check(exc["level"] == "error", "missing level falls back to rule defaultConfiguration")
    check(len(sql["message"]) <= sast.MAX_MESSAGE_LEN, "long message truncated")
    check(sql["engine"] == "semgrep" and sql["source"] == "semgrep", "engine/source recorded")

    capped, gaps = sast.cap_findings(findings * 200, 5)
    check(len(capped) == 5, "cap_findings bounds the list")
    check(len(gaps) == 1 and "dropped" in gaps[0], "dropped rows recorded as a gap note")
    same, no_gap = sast.cap_findings(findings, 5)
    check(same == findings and no_gap == [], "under-cap list passes through untouched")

    with tempfile.TemporaryDirectory() as tmp:
        bad = Path(tmp) / "broken.sarif"
        bad.write_text("{not json", encoding="utf-8")
        good = Path(tmp) / "ok.sarif"
        good.write_text(json.dumps(sample_sarif(root)), encoding="utf-8")
        found, gaps = sast.ingest_sarif_files([bad, good], root)
        check(len(found) == 2, "good SARIF file ingested despite broken sibling")
        check(len(gaps) == 1 and "broken.sarif" in gaps[0], "broken SARIF becomes a gap note")

    with mock.patch.object(sast.shutil, "which", return_value=None):
        found, gaps = sast.run_semgrep(Path("/tmp"))
        check(found == [] and len(gaps) == 1 and "not installed" in gaps[0],
              "missing semgrep degrades to a gap note, never an error")

    # CLI smoke: prescan ingests --sast-sarif and evidence carries the keys.
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        (tmp_path / "app.py").write_text("print('hi')\n", encoding="utf-8")
        sarif_file = tmp_path / "ext.sarif"
        sarif_file.write_text(json.dumps(sample_sarif(tmp_path)), encoding="utf-8")
        proc = subprocess.run(
            [sys.executable, str(THANHTRA_CLI), "prescan", "--root", str(tmp_path),
             "--no-audit", "--sast-sarif", str(sarif_file)],
            capture_output=True, text=True,
        )
        check(proc.returncode == 0, "prescan --sast-sarif exits 0")
        evidence = json.loads(proc.stdout)
        check(len(evidence.get("sast_findings", [])) == 2, "evidence carries ingested sast_findings")
        check(evidence.get("sast_gaps") == [], "no sast gaps for a clean ingest")

        proc2 = subprocess.run(
            [sys.executable, str(THANHTRA_CLI), "prescan", "--root", str(tmp_path), "--no-audit"],
            capture_output=True, text=True,
        )
        evidence2 = json.loads(proc2.stdout)
        check(evidence2.get("sast_findings") == [] and evidence2.get("sast_gaps") == [],
              "without SAST flags the keys exist and stay empty")
        check(evidence2.get("fingerprint_sha256") != evidence.get("fingerprint_sha256"),
              "sast findings change the evidence fingerprint")

    if failures:
        print(f"\n{failures} check(s) failed", file=sys.stderr)
        return 1
    print("\nAll SAST ingest checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
