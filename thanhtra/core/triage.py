#!/usr/bin/env python3
"""Optional LLM triage for Thanh Tra.

The deterministic pre-scan (``thanhtra prescan``) is mechanical: it collects
hotspots, secrets, dependency CVEs. It does NOT decide which hotspot is a real
vulnerability — that needs reasoning (L1-L4 data-flow tracing, false-positive
removal, verdict). Normally a coding agent running the ``/thanhtra`` skill does
that reasoning. This module lets the CLI call an LLM directly instead, so a
full triaged verdict is available headless — in CI, a cron job, or a plain
terminal — without opening an agent.

Provider model:
- "anthropic" (default): calls the Claude Messages API. Uses the official
  ``anthropic`` SDK if installed; otherwise falls back to a stdlib ``urllib``
  call so the CLI keeps its zero-dependency install.

The triage is OPTIONAL. Without an API key the CLI still emits mechanical
evidence exactly as before.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

DEFAULT_MODEL = "claude-opus-4-8"
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
REQUEST_TIMEOUT = 600  # triage reasoning on a large repo can run minutes

# Severity a finding of each rule may receive (mirrors the skill's rule corpus).
CRITICAL_RULES = {
    "HARDCODED-SECRET", "SQL-INJECTION", "SLOPSQUATTING", "MASS-ASSIGNMENT",
    "INSECURE-DESERIALIZATION", "BROKEN-ACCESS-CONTROL", "WEAK-PASSWORD-HASHING",
    "JWT-NONE-ALGORITHM", "UNRESTRICTED-FILE-UPLOAD", "COMMAND-INJECTION",
}
ALL_RULES = sorted(CRITICAL_RULES | {
    "XSS", "IDOR", "BRUTE-FORCE", "SSRF", "PATH-TRAVERSAL", "CSRF",
    "CORS-MISCONFIG", "VERBOSE-ERROR-DEBUG-MODE", "MISSING-RATE-LIMIT",
    "RACE-CONDITION", "OUTDATED-DEPENDENCY", "PROMPT-INJECTION",
})

TRIAGE_SCHEMA = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string", "enum": ["PASS", "WARN", "FAIL"]},
        "summary": {"type": "string"},
        "findings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "rule_id": {"type": "string", "enum": ALL_RULES},
                    "severity": {
                        "type": "string",
                        "enum": ["CRITICAL", "HIGH", "MEDIUM", "LOW"],
                    },
                    "file": {"type": "string"},
                    "line": {"type": "integer"},
                    "title": {"type": "string"},
                    "reasoning": {"type": "string"},
                    "false_positive": {"type": "boolean"},
                    "confidence": {"type": "integer"},
                },
                "required": [
                    "rule_id", "severity", "file", "line",
                    "title", "reasoning", "false_positive", "confidence",
                ],
                "additionalProperties": False,
            },
        },
    },
    "required": ["verdict", "summary", "findings"],
    "additionalProperties": False,
}

SYSTEM_PROMPT = """\
You are Thanh Tra, a security inspector for AI-generated ("vibe") code. You are
given deterministic pre-scan evidence (hotspots, masked secrets, dependency
audit results) collected mechanically from a repository. Your job is to TRIAGE:
decide which signals are real vulnerabilities, assign severity, and set a gate
verdict.

Method — reason, do not pattern-match:
1. For each hotspot, judge whether the matched code is actually exploitable.
   Trace the data source: L1 untrusted input (request/body/params/message,
   file upload) is dangerous; L3/L4 (hardcoded, env, internal constants) is
   usually safe. A hotspot whose value is L3/L4 is a false positive.
2. Mark false positives explicitly (false_positive: true) and exclude them from
   the verdict, but still list them so the operator sees what was dismissed.
3. Map every finding to one of the 22 canonical rule IDs. Severity is capped by
   rule: CRITICAL only for {critical_rules}; all other rules cap at HIGH.
4. Dependency CVEs from the audit are real findings (rule OUTDATED-DEPENDENCY,
   severity HIGH) unless clearly unreachable.

Verdict gate (mechanical — apply exactly):
- Any real (non-false-positive) CRITICAL finding -> FAIL
- Else any real HIGH finding -> WARN
- Else -> PASS

The verdict is the state of the Thanh Tra security gate for this scan scope. It
is NOT a judgment that the app is bad or cannot ship — that is the owner's call.
You triage from evidence snippets only; you cannot open files, so when a snippet
is insufficient to confirm exploitability, lower the confidence and say so in
the reasoning rather than guessing.
"""


def build_messages(evidence: dict, *, max_hotspots: int = 400) -> list[dict]:
    """Build the user message carrying the evidence to triage."""
    hotspots = evidence.get("hotspots_by_rule") or {}
    trimmed: dict[str, list] = {}
    budget = max_hotspots
    for rule_id, items in sorted(hotspots.items()):
        if not items or budget <= 0:
            continue
        take = items[:budget]
        trimmed[rule_id] = take
        budget -= len(take)

    payload = {
        "root": evidence.get("root"),
        "is_git_repo": evidence.get("is_git_repo"),
        "file_count": evidence.get("file_count"),
        "language_counts": evidence.get("language_counts"),
        "dependency_vulnerabilities": evidence.get("dependency_vulnerabilities"),
        "dependency_warnings": evidence.get("dependency_warnings"),
        "audit_gaps": evidence.get("audit_gaps"),
        "secret_hits_masked": evidence.get("secret_hits_masked"),
        "git_secret_signals": evidence.get("git_secret_signals"),
        "docker_exposures": evidence.get("docker_exposures"),
        "hotspots_by_rule": trimmed,
    }
    dropped = sum(len(v) for v in hotspots.values()) - sum(len(v) for v in trimmed.values())
    note = ""
    if dropped > 0:
        note = (
            f"\n\nNote: {dropped} lower-priority hotspot rows were omitted to fit "
            "the triage budget; judge from the rows provided."
        )
    text = (
        "Triage this deterministic pre-scan evidence and return the structured "
        "verdict.\n\n```json\n"
        + json.dumps(payload, ensure_ascii=False, indent=2)
        + "\n```"
        + note
    )
    return [{"role": "user", "content": text}]


def build_request_body(evidence: dict, model: str) -> dict:
    return {
        "model": model,
        "max_tokens": 16000,
        "system": SYSTEM_PROMPT.format(critical_rules=", ".join(sorted(CRITICAL_RULES))),
        "thinking": {"type": "adaptive"},
        "output_config": {
            "effort": "high",
            "format": {"type": "json_schema", "schema": TRIAGE_SCHEMA},
        },
        "messages": build_messages(evidence),
    }


class TriageError(RuntimeError):
    """Raised when triage cannot complete (no key, API error, refusal)."""


def _first_text_block(content: list) -> str:
    for block in content:
        if isinstance(block, dict) and block.get("type") == "text":
            return block.get("text", "")
    raise TriageError("no text block in model response")


def _call_anthropic_sdk(body: dict, api_key: str):
    try:
        import anthropic  # noqa: PLC0415
    except ImportError:
        return None
    client = anthropic.Anthropic(api_key=api_key)
    resp = client.messages.create(**body)
    if resp.stop_reason == "refusal":
        raise TriageError("model refused the triage request")
    for block in resp.content:
        if getattr(block, "type", None) == "text":
            return json.loads(block.text)
    raise TriageError("no text block in model response")


def _call_anthropic_http(body: dict, api_key: str) -> dict:
    request = urllib.request.Request(
        ANTHROPIC_URL,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "content-type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": ANTHROPIC_VERSION,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:  # noqa: PERF203
        detail = exc.read().decode("utf-8", "ignore")
        raise TriageError(f"Anthropic API error {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise TriageError(f"network error calling Anthropic API: {exc.reason}") from exc

    if data.get("stop_reason") == "refusal":
        raise TriageError("model refused the triage request")
    return json.loads(_first_text_block(data.get("content", [])))


def triage(evidence: dict, *, provider: str | None = None, model: str | None = None) -> dict:
    """Run LLM triage over deterministic evidence. Returns a verdict document.

    Raises TriageError if the provider is unknown, the API key is missing, or
    the API call fails. Callers should let the mechanical scan succeed even if
    triage raises.
    """
    provider = provider or os.environ.get("THANHTRA_TRIAGE_PROVIDER", "anthropic")
    model = model or os.environ.get("THANHTRA_TRIAGE_MODEL", DEFAULT_MODEL)

    if provider != "anthropic":
        raise TriageError(f"unknown triage provider: {provider!r} (only 'anthropic' supported)")

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise TriageError(
            "ANTHROPIC_API_KEY not set — triage needs an API key. "
            "Run without --triage for mechanical evidence only."
        )

    body = build_request_body(evidence, model)
    result = _call_anthropic_sdk(body, api_key)
    if result is None:  # SDK not installed → stdlib fallback
        result = _call_anthropic_http(body, api_key)

    result["provider"] = provider
    result["model"] = model
    return result
