"""Command-line interface for Thanh Tra."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from thanhtra import __version__
from thanhtra.core.prescan import build_evidence
from thanhtra.core.sarif import to_sarif
from thanhtra.core.triage import TriageError, triage as run_triage


def hotspot_counts(evidence: dict) -> dict[str, int]:
    return {
        rule_id: len(items)
        for rule_id, items in sorted((evidence.get("hotspots_by_rule") or {}).items())
        if items
    }


def build_scan_document(args: argparse.Namespace, evidence: dict) -> dict:
    summary = {
        "file_count": evidence.get("file_count", 0),
        "hotspot_file_count": evidence.get("hotspot_file_count", 0),
        "file_kind_counts": evidence.get("file_kind_counts", {}),
        "language_counts": evidence.get("language_counts", {}),
        "dependency_file_count": len(evidence.get("dependency_files", [])),
        "dependency_vulnerability_count": len(evidence.get("dependency_vulnerabilities", [])),
        "dependency_warning_count": len(evidence.get("dependency_warnings", [])),
        "audit_gap_count": len(evidence.get("audit_gaps", [])),
        "secret_hit_count": len(evidence.get("secret_hits_masked", [])),
        "git_secret_signal_count": len(evidence.get("git_secret_signals", [])),
        "docker_exposure_count": len(evidence.get("docker_exposures", [])),
        "agent_trust_signal_count": len(evidence.get("agent_trust_signals", [])),
        "sast_finding_count": len(evidence.get("sast_findings", [])),
        "sast_gap_count": len(evidence.get("sast_gaps", [])),
        "hotspot_counts": hotspot_counts(evidence),
    }
    return {
        "schema": "thanhtra-scan/v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "root": str(Path(args.root).resolve()),
        "mode": "pre-scan",
        "summary": summary,
        "evidence": evidence,
    }


def scan(args: argparse.Namespace) -> int:
    sarif = getattr(args, "sarif", False)
    evidence = build_evidence(
        Path(args.root),
        max_per_rule=args.max_per_rule,
        max_secrets=args.max_secrets,
        no_audit=args.no_audit,
        semgrep=args.semgrep,
        semgrep_config=args.semgrep_config,
        sast_sarif=args.sast_sarif,
        max_sast=args.max_sast,
    )
    document = build_scan_document(args, evidence)
    if sarif or getattr(args, "triage", False):
        # Triage is best-effort: a failure must not lose the mechanical evidence.
        try:
            document["triage"] = run_triage(
                evidence,
                provider=args.triage_provider,
                model=args.triage_model,
                base_url=args.triage_base_url,
            )
            document["summary"]["verdict"] = document["triage"].get("verdict")
        except TriageError as exc:
            document["triage_error"] = str(exc)
            print(f"thanhtra: triage skipped: {exc}", file=sys.stderr)
            if sarif:
                # SARIF maps triage findings; without a verdict the CI gate
                # must fail loudly, not upload an empty (= all-clear) log.
                print("thanhtra: --sarif needs a triage verdict, aborting", file=sys.stderr)
                return 1
    payload = to_sarif(document) if sarif else document
    output = json.dumps(payload, ensure_ascii=False, indent=None if args.compact else 2)
    if args.output:
        output_path = Path(args.output)
        if not output_path.is_absolute():
            output_path = Path(args.root).resolve() / output_path
        output_path.write_text(output + "\n", encoding="utf-8")
    if args.json or not args.output:
        sys.stdout.write(output + "\n")
    return 0


def triage_cmd(args: argparse.Namespace) -> int:
    if args.evidence and args.evidence != "-":
        evidence = json.loads(Path(args.evidence).read_text(encoding="utf-8"))
    elif not sys.stdin.isatty():
        evidence = json.loads(sys.stdin.read())
    else:
        # No evidence supplied: run a pre-scan on --root first.
        evidence = build_evidence(Path(args.root), no_audit=args.no_audit)
    # A scan document wraps evidence under "evidence"; accept either shape.
    if "hotspots_by_rule" not in evidence and isinstance(evidence.get("evidence"), dict):
        evidence = evidence["evidence"]
    document = run_triage(
        evidence,
        provider=args.triage_provider,
        model=args.triage_model,
        base_url=args.triage_base_url,
    )
    sys.stdout.write(json.dumps(document, ensure_ascii=False, indent=2) + "\n")
    return 0


def prescan(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    evidence = build_evidence(
        root,
        max_per_rule=args.max_per_rule,
        max_secrets=args.max_secrets,
        no_audit=args.no_audit,
        semgrep=args.semgrep,
        semgrep_config=args.semgrep_config,
        sast_sarif=args.sast_sarif,
        max_sast=args.max_sast,
    )
    output = json.dumps(evidence, ensure_ascii=False, indent=None if args.compact else 2)
    if args.output:
        output_path = Path(args.output)
        if not output_path.is_absolute():
            output_path = root / output_path
        output_path.write_text(output + "\n", encoding="utf-8")
    else:
        sys.stdout.write(output + "\n")
    return 0


def add_sast_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--semgrep",
        action="store_true",
        help="run semgrep as an extra SAST backend if installed (best-effort)",
    )
    parser.add_argument(
        "--semgrep-config",
        default=os.environ.get("THANHTRA_SEMGREP_CONFIG"),
        help="semgrep ruleset (default p/default; 'auto' needs semgrep metrics on)",
    )
    parser.add_argument(
        "--sast-sarif",
        action="append",
        metavar="PATH",
        help="ingest findings from an existing SARIF file (repeatable, any engine)",
    )
    parser.add_argument("--max-sast", type=int, default=200)


def build_parser(prog: str = "thanhtra") -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog=prog)
    parser.add_argument("--version", action="version", version=f"Thanh Tra {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    scan_parser = subparsers.add_parser("scan", help="scan a repository/folder and emit JSON")
    scan_parser.add_argument("root", nargs="?", default=".", help="repo/folder root to scan")
    scan_parser.add_argument("--json", action="store_true", help="print JSON to stdout")
    scan_parser.add_argument("--output", help="write JSON to this path")
    scan_parser.add_argument("--compact", action="store_true", help="emit compact JSON")
    scan_parser.add_argument("--no-audit", action="store_true", help="skip dependency audit commands")
    scan_parser.add_argument("--max-per-rule", type=int, default=80)
    scan_parser.add_argument("--max-secrets", type=int, default=100)
    add_sast_args(scan_parser)
    scan_parser.add_argument(
        "--triage",
        action="store_true",
        help="reason over the evidence with an LLM (needs ANTHROPIC_API_KEY) "
        "to produce a verdict + findings, not just mechanical evidence",
    )
    scan_parser.add_argument("--triage-model", help="override triage model (default claude-opus-4-8)")
    scan_parser.add_argument("--triage-provider", help="triage provider: anthropic (default) or openai")
    scan_parser.add_argument("--triage-base-url", help="OpenAI-compatible base URL (e.g. OpenRouter, Ollama)")
    scan_parser.add_argument(
        "--sarif",
        action="store_true",
        help="emit SARIF 2.1.0 instead of scan JSON (implies --triage; for "
        "GitHub code scanning via codeql-action/upload-sarif)",
    )
    scan_parser.set_defaults(func=scan)

    triage_parser = subparsers.add_parser(
        "triage", help="LLM-triage existing evidence into a verdict (needs ANTHROPIC_API_KEY)"
    )
    triage_parser.add_argument(
        "--evidence", help="path to a prescan/scan JSON file, or '-' for stdin"
    )
    triage_parser.add_argument("--root", default=".", help="repo to pre-scan if no --evidence given")
    triage_parser.add_argument("--no-audit", action="store_true", help="skip dependency audit when pre-scanning")
    triage_parser.add_argument("--triage-model", help="override triage model (default claude-opus-4-8)")
    triage_parser.add_argument("--triage-provider", help="triage provider: anthropic (default) or openai")
    triage_parser.add_argument("--triage-base-url", help="OpenAI-compatible base URL (e.g. OpenRouter, Ollama)")
    triage_parser.set_defaults(func=triage_cmd)

    prescan_parser = subparsers.add_parser(
        "prescan", help="emit raw pre-scan evidence JSON (thanhtra-pre-scan/v1)"
    )
    prescan_parser.add_argument("--root", default=".", help="repo/folder root to scan")
    prescan_parser.add_argument("--output", help="write JSON evidence to this path instead of stdout")
    prescan_parser.add_argument("--compact", action="store_true", help="emit compact JSON")
    prescan_parser.add_argument("--no-audit", action="store_true", help="skip dependency audit commands")
    prescan_parser.add_argument("--max-per-rule", type=int, default=80)
    prescan_parser.add_argument("--max-secrets", type=int, default=100)
    add_sast_args(prescan_parser)
    prescan_parser.set_defaults(func=prescan)
    return parser


def main(argv: list[str] | None = None, *, prog: str = "thanhtra") -> int:
    parser = build_parser(prog)
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except Exception as exc:  # noqa: BLE001
        print(f"{prog}: error: {exc}", file=sys.stderr)
        return 1
