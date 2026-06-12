#!/usr/bin/env python3
"""Validate Thanh Tra fixture metadata.

This does not run an LLM security scan. It verifies that regression fixtures and
their expected findings are structurally sound, so future scan harnesses have a
stable corpus to run against.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPECTED = ROOT / "tests" / "expected-findings.json"
RULE_DIR = ROOT / "skills" / "thanhtra" / "rules" / "generic"
VALID_SEVERITIES = {"CRITICAL", "HIGH", "MEDIUM", "LOW"}
VALID_LANGUAGES = {"go", "php", "python", "typescript", "rust", "swift", "shell", "generic"}


def fail(message: str) -> None:
    print(f"FAIL: {message}", file=sys.stderr)


def ok(message: str) -> None:
    print(f"OK: {message}")


def load_rule_ids() -> set[str]:
    ids: set[str] = set()
    for path in sorted(RULE_DIR.glob("[0-9][0-9]-*.md")):
        text = path.read_text(encoding="utf-8")
        match = re.search(r"^id:\s*([A-Z0-9-]+)\s*$", text, re.MULTILINE)
        if match:
            ids.add(match.group(1))
    return ids


def line_count(path: Path) -> int:
    return len(path.read_text(encoding="utf-8").splitlines())


def main() -> int:
    errors = 0

    if not EXPECTED.exists():
        fail(f"missing expected findings manifest: {EXPECTED}")
        return 1

    data = json.loads(EXPECTED.read_text(encoding="utf-8"))
    cases = data.get("cases")
    if not isinstance(cases, list) or not cases:
        fail("tests/expected-findings.json must contain a non-empty cases array")
        return 1

    rule_ids = load_rule_ids()
    if len(rule_ids) != 22:
        fail(f"loaded {len(rule_ids)} canonical rule IDs, expected 22")
        errors += 1
    else:
        ok("loaded 22 canonical rule IDs")

    names: set[str] = set()
    positive_count = 0
    negative_count = 0
    finding_count = 0

    for case in cases:
        name = case.get("name")
        rel_path = case.get("path")
        language = case.get("language")
        findings = case.get("expected_findings")

        if not isinstance(name, str) or not name:
            fail("fixture case missing name")
            errors += 1
            continue
        if name in names:
            fail(f"duplicate fixture case name: {name}")
            errors += 1
        names.add(name)

        if language not in VALID_LANGUAGES:
            fail(f"{name}: invalid language {language!r}")
            errors += 1

        if not isinstance(rel_path, str):
            fail(f"{name}: missing path")
            errors += 1
            continue

        case_dir = ROOT / rel_path
        if not case_dir.is_dir():
            fail(f"{name}: fixture directory missing: {rel_path}")
            errors += 1
            continue

        code_files = [
            path
            for path in case_dir.rglob("*")
            if path.is_file()
            and path.suffix in {".go", ".php", ".py", ".js", ".jsx", ".ts", ".tsx", ".rs", ".swift", ".sh"}
        ]
        if not code_files:
            fail(f"{name}: fixture contains no source files")
            errors += 1

        if not isinstance(findings, list):
            fail(f"{name}: expected_findings must be an array")
            errors += 1
            continue

        if name.startswith("positive/"):
            positive_count += 1
            if not findings:
                fail(f"{name}: positive fixture must contain at least one expected finding")
                errors += 1
        elif name.startswith("negative/"):
            negative_count += 1
            if findings:
                fail(f"{name}: negative fixture must not contain expected findings")
                errors += 1
        else:
            fail(f"{name}: fixture name must start with positive/ or negative/")
            errors += 1

        for finding in findings:
            finding_count += 1
            rule_id = finding.get("rule_id")
            severity = finding.get("severity")
            file_name = finding.get("file")
            line = finding.get("line")

            if rule_id not in rule_ids:
                fail(f"{name}: unknown rule_id {rule_id!r}")
                errors += 1

            if severity not in VALID_SEVERITIES:
                fail(f"{name}: invalid severity {severity!r}")
                errors += 1

            if not isinstance(file_name, str):
                fail(f"{name}: finding missing file")
                errors += 1
                continue

            target_file = case_dir / file_name
            if not target_file.is_file():
                fail(f"{name}: expected finding file missing: {file_name}")
                errors += 1
                continue

            if not isinstance(line, int) or line < 1:
                fail(f"{name}: invalid line {line!r}")
                errors += 1
                continue

            max_line = line_count(target_file)
            if line > max_line:
                fail(f"{name}: expected line {line} exceeds {file_name} length {max_line}")
                errors += 1

    if positive_count == 0 or negative_count == 0:
        fail("fixture corpus must include both positive and negative cases")
        errors += 1
    else:
        ok(f"fixture corpus includes {positive_count} positive and {negative_count} negative cases")

    ok(f"validated {finding_count} expected positive finding(s)")

    if errors:
        print(f"\nFixture validation failed with {errors} issue(s).", file=sys.stderr)
        return 1

    print("\nFixture validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
