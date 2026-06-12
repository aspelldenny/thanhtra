"""External SAST ingestion for the Thanh Tra pre-scan.

The pre-scan's own hotspot collection is grep-pattern: it guides the LLM
triage but does no dataflow. A real SAST engine (semgrep, CodeQL, anything
that speaks SARIF) catches a different class of signal. This module wires
such engines in as an optional *pre-scan backend*: their findings become
deterministic evidence feeding the same L1-L4 triage as the grep hotspots —
augmenting, not replacing them.

Two entry points, mirroring the dependency-audit philosophy (mechanical,
best-effort, no model):

- ``ingest_sarif_files``: normalize findings from existing SARIF files
  (any engine — run it yourself, hand Thanh Tra the output).
- ``run_semgrep``: run semgrep directly when it is installed; a missing or
  failing semgrep is recorded as a gap note, never an error.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

SEMGREP_TIMEOUT = 600  # full-repo semgrep on a large codebase can run minutes
DEFAULT_SEMGREP_CONFIG = "p/default"  # explicit registry pack: works with --metrics=off
MAX_MESSAGE_LEN = 300


def _truncate(text: str) -> str:
    text = " ".join(text.split())
    if len(text) > MAX_MESSAGE_LEN:
        return text[: MAX_MESSAGE_LEN - 1] + "…"
    return text


def _relative_uri(uri: str, root: Path) -> str:
    uri = uri.replace("\\", "/")
    if uri.startswith("file://"):
        uri = uri[len("file://"):]
    try:
        return str(Path(uri).resolve().relative_to(root.resolve()))
    except ValueError:
        while uri.startswith("./"):
            uri = uri[2:]
        return uri.lstrip("/")


def normalize_sarif(sarif: dict, *, source: str, root: Path) -> list[dict]:
    """Flatten a SARIF log into Thanh Tra's normalized SAST finding rows."""
    findings = []
    for run in sarif.get("runs") or []:
        driver = (run.get("tool") or {}).get("driver") or {}
        engine = driver.get("name") or source
        default_levels = {
            rule.get("id"): (rule.get("defaultConfiguration") or {}).get("level")
            for rule in driver.get("rules") or []
        }
        for result in run.get("results") or []:
            if result.get("suppressions"):
                continue
            rule_id = result.get("ruleId") or ""
            location = {}
            for loc in result.get("locations") or []:
                location = loc.get("physicalLocation") or {}
                if location:
                    break
            uri = (location.get("artifactLocation") or {}).get("uri") or ""
            line = (location.get("region") or {}).get("startLine") or 1
            findings.append({
                "engine": engine,
                "source": source,
                "rule_id": rule_id,
                "level": result.get("level") or default_levels.get(rule_id) or "warning",
                "file": _relative_uri(uri, root),
                "line": int(line),
                "message": _truncate((result.get("message") or {}).get("text") or rule_id),
            })
    return findings


def ingest_sarif_files(paths: list[Path], root: Path) -> tuple[list[dict], list[str]]:
    """Parse external SARIF files. Unreadable files become gap notes."""
    findings: list[dict] = []
    gaps: list[str] = []
    for path in paths:
        try:
            sarif = json.loads(path.read_text(encoding="utf-8"))
            findings.extend(normalize_sarif(sarif, source=path.name, root=root))
        except (OSError, ValueError) as exc:
            gaps.append(f"sast-sarif: cannot ingest {path}: {exc}")
    return findings, gaps


def run_semgrep(
    root: Path,
    *,
    config: str | None = None,
    timeout: int = SEMGREP_TIMEOUT,
) -> tuple[list[dict], list[str]]:
    """Run semgrep as a pre-scan backend. Best-effort: missing tool → gap note."""
    if shutil.which("semgrep") is None:
        return [], [
            "semgrep not installed — SAST backend skipped "
            "(pipx install semgrep, or pass --sast-sarif with output from another engine)"
        ]
    config = config or DEFAULT_SEMGREP_CONFIG
    with tempfile.TemporaryDirectory() as tmp:
        out_path = Path(tmp) / "semgrep.sarif"
        cmd = [
            "semgrep", "scan",
            "--config", config,
            "--sarif", "--output", str(out_path),
            "--metrics", "off",
            "--quiet",
        ]
        try:
            proc = subprocess.run(
                cmd, cwd=root, capture_output=True, text=True, timeout=timeout, check=False
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return [], [f"semgrep: failed to run: {exc}"]
        # semgrep exits 1 when findings exist with --error; without it 0/2+ split:
        # treat "no output file" as the failure signal rather than the exit code.
        if not out_path.exists():
            detail = _truncate(proc.stderr or proc.stdout or f"exit {proc.returncode}")
            return [], [f"semgrep: no SARIF produced ({detail})"]
        try:
            sarif = json.loads(out_path.read_text(encoding="utf-8"))
        except ValueError as exc:
            return [], [f"semgrep: unparseable SARIF: {exc}"]
    return normalize_sarif(sarif, source="semgrep", root=root), []


def cap_findings(findings: list[dict], max_findings: int) -> tuple[list[dict], list[str]]:
    """Bound evidence size; the dropped count is recorded, never silent."""
    if len(findings) <= max_findings:
        return findings, []
    kept = findings[:max_findings]
    return kept, [
        f"sast: {len(findings) - max_findings} finding rows beyond the first "
        f"{max_findings} were dropped from evidence (raise --max-sast to keep more)"
    ]
