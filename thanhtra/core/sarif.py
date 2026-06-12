"""SARIF 2.1.0 output for Thanh Tra.

Converts a triaged scan document (``thanhtra scan --triage``) into SARIF so
findings show up natively in GitHub's Security tab and as inline PR
annotations via ``github/codeql-action/upload-sarif``.

The mapping is over the *triage* findings, not the raw pre-scan hotspots:
hotspots are mechanical signals with no exploitability judgment, and pushing
them unfiltered into code scanning would bury real findings in noise. False
positives the triage explicitly dismissed are excluded from ``results[]``
(GitHub would otherwise open alerts for them) and counted in
``run.properties.dismissed_false_positives`` — the full list stays in the
scan JSON.
"""

from __future__ import annotations

from thanhtra import __version__

SARIF_VERSION = "2.1.0"
SARIF_SCHEMA = "https://docs.oasis-open.org/sarif/sarif/v2.1.0/errata01/os/schemas/sarif-schema-2.1.0.json"
INFO_URI = "https://github.com/aspelldenny/thanhtra"
RULE_DOC_BASE = f"{INFO_URI}/blob/main/skills/thanhtra/rules/generic"

# severity → SARIF level. CRITICAL has no SARIF analogue above error; the
# original severity is preserved per-result in properties.severity.
LEVEL_BY_SEVERITY = {
    "CRITICAL": "error",
    "HIGH": "error",
    "MEDIUM": "warning",
    "LOW": "note",
}

# GitHub reads rule properties."security-severity" (CVSS-like 0–10) to bucket
# alerts: >=9.0 critical, 7.0–8.9 high.
SECURITY_SEVERITY = {"CRITICAL": "9.1", "HIGH": "7.5"}

# The 22 canonical rules, in corpus order (NN matches the rule file prefix).
# severity_max mirrors CRITICAL_RULES in triage.py.
RULES: list[tuple[str, str, str]] = [
    ("HARDCODED-SECRET", "CRITICAL", "API key, DB password, or token embedded in source or committed to git."),
    ("SQL-INJECTION", "CRITICAL", "Untrusted input concatenated or interpolated into SQL queries."),
    ("XSS", "HIGH", "Untrusted input rendered into HTML/JS without encoding or sanitization."),
    ("IDOR", "HIGH", "Object accessed by client-supplied ID without an ownership check."),
    ("SLOPSQUATTING", "CRITICAL", "Dependency on a non-existent or typo-squatted package name (AI-hallucinated imports)."),
    ("BRUTE-FORCE", "HIGH", "Authentication endpoint without lockout, throttling, or attempt limits."),
    ("MASS-ASSIGNMENT", "CRITICAL", "Request body bound directly to a model, letting clients set privileged fields."),
    ("INSECURE-DESERIALIZATION", "CRITICAL", "Untrusted data deserialized with an unsafe loader (pickle, unserialize, NSKeyedUnarchiver...)."),
    ("SSRF", "HIGH", "Server-side request to a URL influenced by untrusted input."),
    ("PATH-TRAVERSAL", "HIGH", "File path built from untrusted input without normalization/containment."),
    ("CSRF", "HIGH", "State-changing endpoint without CSRF protection."),
    ("BROKEN-ACCESS-CONTROL", "CRITICAL", "Missing or bypassable authorization on a protected operation."),
    ("WEAK-PASSWORD-HASHING", "CRITICAL", "Passwords stored with fast or broken hashes (MD5/SHA1/plain) instead of bcrypt/argon2."),
    ("JWT-NONE-ALGORITHM", "CRITICAL", "JWT verification accepting 'none' or attacker-chosen algorithms."),
    ("CORS-MISCONFIG", "HIGH", "CORS policy reflecting arbitrary origins or combining wildcard with credentials."),
    ("UNRESTRICTED-FILE-UPLOAD", "CRITICAL", "File upload without type/size/path restrictions, enabling webshell or overwrite."),
    ("VERBOSE-ERROR-DEBUG-MODE", "HIGH", "Debug mode or verbose stack traces exposed in production."),
    ("MISSING-RATE-LIMIT", "HIGH", "Expensive or sensitive endpoint without rate limiting."),
    ("RACE-CONDITION", "HIGH", "Check-then-act on shared state without locking/transaction (double-spend class)."),
    ("OUTDATED-DEPENDENCY", "HIGH", "Dependency with known CVEs reported by the ecosystem audit tool."),
    ("COMMAND-INJECTION", "CRITICAL", "Untrusted input reaching a shell or process invocation."),
    ("PROMPT-INJECTION", "HIGH", "Untrusted content reaching an LLM prompt or agent context without isolation (direct or context-poisoning)."),
]

_RULE_INDEX = {rule_id: i for i, (rule_id, _, _) in enumerate(RULES)}


def _rule_doc_uri(rule_id: str) -> str:
    number = _RULE_INDEX[rule_id] + 1
    return f"{RULE_DOC_BASE}/{number:02d}-{rule_id.lower()}.md"


def _pascal_name(rule_id: str) -> str:
    return "".join(part.capitalize() for part in rule_id.split("-"))


def build_rules() -> list[dict]:
    rules = []
    for rule_id, severity_max, description in RULES:
        rules.append({
            "id": rule_id,
            "name": _pascal_name(rule_id),
            "shortDescription": {"text": description},
            "helpUri": _rule_doc_uri(rule_id),
            "defaultConfiguration": {"level": LEVEL_BY_SEVERITY[severity_max]},
            "properties": {
                "severity_max": severity_max,
                "security-severity": SECURITY_SEVERITY[severity_max],
                "tags": ["security"],
            },
        })
    return rules


def _normalize_uri(file: str) -> str:
    # SARIF artifactLocation.uri is relative to the scanned root; the pre-scan
    # already records root-relative paths, so just strip "./" and use "/".
    uri = file.replace("\\", "/")
    while uri.startswith("./"):
        uri = uri[2:]
    return uri.lstrip("/")


def _to_result(finding: dict) -> dict:
    rule_id = finding.get("rule_id", "")
    severity = finding.get("severity", "MEDIUM")
    title = finding.get("title", "")
    reasoning = finding.get("reasoning", "")
    message = f"{title} — {reasoning}" if title and reasoning else (title or reasoning or rule_id)
    result = {
        "ruleId": rule_id,
        "level": LEVEL_BY_SEVERITY.get(severity, "warning"),
        "message": {"text": message},
        "locations": [{
            "physicalLocation": {
                "artifactLocation": {"uri": _normalize_uri(finding.get("file", ""))},
                "region": {"startLine": max(1, int(finding.get("line") or 1))},
            },
        }],
        "properties": {
            "severity": severity,
            "confidence": finding.get("confidence"),
        },
    }
    if rule_id in _RULE_INDEX:
        result["ruleIndex"] = _RULE_INDEX[rule_id]
    return result


def to_sarif(document: dict) -> dict:
    """Convert a thanhtra-scan/v1 document with triage into a SARIF log."""
    triage = document.get("triage")
    if not isinstance(triage, dict):
        raise ValueError(
            "scan document has no triage section — SARIF maps triage findings, "
            "run with --triage (the --sarif flag implies it)"
        )
    findings = triage.get("findings") or []
    real = [f for f in findings if not f.get("false_positive")]
    dismissed = len(findings) - len(real)

    run = {
        "tool": {
            "driver": {
                "name": "Thanh Tra",
                "semanticVersion": __version__,
                "informationUri": INFO_URI,
                "rules": build_rules(),
            },
        },
        "results": [_to_result(f) for f in real],
        "properties": {
            "verdict": triage.get("verdict"),
            "summary": triage.get("summary"),
            "triage_provider": triage.get("provider"),
            "triage_model": triage.get("model"),
            "dismissed_false_positives": dismissed,
            "generated_at": document.get("generated_at"),
        },
    }
    return {
        "$schema": SARIF_SCHEMA,
        "version": SARIF_VERSION,
        "runs": [run],
    }
