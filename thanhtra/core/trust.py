"""Agent-trust signals: detect repo content that targets AI coding agents.

Threat class ("Rules File Backdoor", Pillar Security 2025; ToxicSkills, Snyk
2026): a cloned repo carries payloads aimed not at the compiler but at the
*AI agent* a developer opens inside it — invisible Unicode in instruction
files the agent auto-reads, configs that auto-execute commands when the
folder is trusted, or natural-language injection in agent-consumed markdown.

This detector is deliberately deterministic (no model): it can be run on an
untrusted folder BEFORE any LLM reads its content, because regexes cannot be
prompt-injected. Three signal classes, each mapped to its OWASP Top 10 for
Agentic Applications 2026 (ASI) category:

- ``hidden-unicode`` [ASI06 Memory & Context Poisoning]: invisible/bidi
  codepoints in any text file — Tags block (U+E0000–E007F), zero-width
  (U+200B–D, U+2060, U+FEFF, U+2063), bidi controls (U+202A–E, U+2066–69),
  private use areas. VS15/VS16 are exempt (legitimate emoji selectors).
- ``auto-exec`` [ASI05 Unexpected Code Execution]: configs that run or load
  commands when the folder is opened or trusted — agent hooks, project MCP
  servers, folder-open tasks, devcontainer lifecycle commands, direnv,
  package-manager lifecycle scripts, committed git-hook managers.
- ``injection-marker`` [ASI01 Agent Goal Hijack]: imperative-injection
  phrases, curl|sh, or large base64 blobs inside files agents auto-read as
  instructions. Heuristic (visible text can also be judged by a human/
  triage), so callers usually treat these as review tripwires, not hard
  failures.

Two framework categories are covered at the system level rather than by a
single signal type: the whole ``agent_trust_signals`` evidence stream plus
the CI trust gate is the repo's defense against **ASI04 Agentic Supply Chain
Compromise**, and running this deterministic prescan *before* an agent trusts
a cloned folder is the mitigation for **ASI09 Human-Agent Trust
Exploitation**.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

MAX_SIGNALS = 200
MAX_FILE_BYTES = 2_000_000

# Invisible/control codepoints with essentially no legitimate use in source
# or markdown. VS15/16 (U+FE0E/F) excluded: common after emoji.
HIDDEN_UNICODE_RE = re.compile(
    "["
    "\U000E0000-\U000E007F"  # Tags block (ASCII smuggling)
    "\u200b-\u200d"        # zero-width space/non-joiner/joiner
    "\u2060\ufeff\u2063"    # word joiner, BOM-as-ZWNBSP, invisible separator
    "\u202a-\u202e"        # bidi embeddings/overrides (Trojan Source)
    "\u2066-\u2069"        # bidi isolates
    "\ue000-\uf8ff"        # private use area (BMP)
    "\U000F0000-\U000FFFFD"  # private use plane 15
    "\U00100000-\U0010FFFD"  # private use plane 16
    "]"
)

# Files AI agents auto-read as instructions when opened in a repo.
AGENT_INSTRUCTION_NAMES = {
    "claude.md", "claude.local.md", "agents.md", "gemini.md", "skill.md",
    ".cursorrules", ".windsurfrules", ".clinerules",
}
AGENT_INSTRUCTION_PATTERNS = (
    re.compile(r"(^|/)\.github/copilot-instructions\.md$"),
    re.compile(r"(^|/)\.cursor/rules/[^/]+\.mdc$"),
    re.compile(r"(^|/)\.claude/commands/[^/]+\.md$"),
    re.compile(r"(^|/)\.agent/"),
)

INJECTION_MARKERS = (
    ("override-instructions",
     re.compile(r"(ignore|disregard|forget)\s+(all\s+)?(previous|prior|earlier|above|system)\s+"
                r"(instructions?|rules?|prompts?|guidelines?)", re.IGNORECASE)),
    ("hide-from-user",
     re.compile(r"do(\s+not|n't)\s+(tell|inform|mention|reveal|show|disclose)\s+"
                r"(this\s+)?(to\s+)?(the\s+)?(user|developer|human|operator)", re.IGNORECASE)),
    ("pipe-to-shell",
     re.compile(r"\b(curl|wget)\b[^\n|]{0,200}\|\s*(sudo\s+)?(ba|z)?sh\b", re.IGNORECASE)),
    ("base64-blob",
     re.compile(r"[A-Za-z0-9+/]{120,}={0,2}")),
)


def is_agent_instruction_file(rel: str) -> bool:
    rel_norm = rel.replace("\\", "/")
    if Path(rel_norm).name.lower() in AGENT_INSTRUCTION_NAMES:
        return True
    return any(p.search(rel_norm) for p in AGENT_INSTRUCTION_PATTERNS)


def _read_text(path: Path) -> str | None:
    try:
        if path.stat().st_size > MAX_FILE_BYTES:
            return None
        raw = path.read_bytes()
    except OSError:
        return None
    if b"\x00" in raw[:8000]:  # binary
        return None
    return raw.decode("utf-8", errors="ignore")


def _signal(kind: str, path: str, line: int, detail: str) -> dict:
    return {"type": kind, "path": path, "line": line, "detail": detail}


def scan_hidden_unicode(rel: str, text: str) -> list[dict]:
    signals = []
    for lineno, line in enumerate(text.splitlines(), 1):
        hits = HIDDEN_UNICODE_RE.findall(line)
        if hits:
            codepoints = ", ".join(sorted({f"U+{ord(c):04X}" for c in hits}))
            signals.append(_signal(
                "hidden-unicode", rel, lineno,
                f"{len(hits)} invisible codepoint(s): {codepoints}",
            ))
    return signals


def scan_injection_markers(rel: str, text: str) -> list[dict]:
    signals = []
    for lineno, line in enumerate(text.splitlines(), 1):
        for kind, pattern in INJECTION_MARKERS:
            if pattern.search(line):
                signals.append(_signal(
                    "injection-marker", rel, lineno,
                    f"{kind} in agent-read instruction file",
                ))
    return signals


def _json_or_none(text: str) -> dict | None:
    try:
        data = json.loads(text)
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def scan_auto_exec(rel: str, text: str) -> list[dict]:
    """Flag configs that execute or load something on folder open/trust."""
    rel_norm = rel.replace("\\", "/")
    name = Path(rel_norm).name
    signals = []

    if rel_norm.endswith((".claude/settings.json", ".claude/settings.local.json")):
        data = _json_or_none(text) or {}
        if data.get("hooks"):
            signals.append(_signal(
                "auto-exec", rel, 1,
                "Claude Code project hooks — shell commands run on agent events once the folder is trusted",
            ))
        if data.get("statusLine"):
            signals.append(_signal(
                "auto-exec", rel, 1,
                "Claude Code statusLine command — repo-supplied shell runs automatically once trusted",
            ))
        if (data.get("permissions") or {}).get("allow"):
            signals.append(_signal(
                "auto-exec", rel, 1,
                "Claude Code permissions.allow — repo pre-allowlists commands so they run without prompts",
            ))
    elif rel_norm.endswith(".codex/hooks.json"):
        signals.append(_signal(
            "auto-exec", rel, 1,
            "Codex project hooks — shell on agent events (double consent required, still review)",
        ))
    elif name == ".mcp.json":
        signals.append(_signal(
            "auto-exec", rel, 1,
            "project-scoped MCP servers — local processes the agent is asked to start",
        ))
    elif rel_norm.endswith(".vscode/tasks.json") and "folderOpen" in text:
        signals.append(_signal(
            "auto-exec", rel, 1,
            'VS Code task with "runOn": "folderOpen" — executes when the folder is opened (after trust)',
        ))
    elif name == "devcontainer.json":
        lifecycle = re.findall(
            r'"(initializeCommand|onCreateCommand|updateContentCommand|postCreateCommand|'
            r'postStartCommand|postAttachCommand)"', text)
        if lifecycle:
            signals.append(_signal(
                "auto-exec", rel, 1,
                f"devcontainer lifecycle command(s): {', '.join(sorted(set(lifecycle)))}",
            ))
    elif name == ".envrc":
        signals.append(_signal(
            "auto-exec", rel, 1,
            "direnv .envrc — shell sourced on cd for direnv users (after direnv allow)",
        ))
    elif name == "package.json" and "node_modules" not in rel_norm:
        data = _json_or_none(text) or {}
        scripts = data.get("scripts") or {}
        lifecycle = sorted(k for k in scripts if k in {
            "preinstall", "install", "postinstall", "prepare", "prepublish",
        })
        if lifecycle:
            signals.append(_signal(
                "auto-exec", rel, 1,
                f"npm lifecycle script(s) run on install: {', '.join(lifecycle)}",
            ))
    elif re.search(r"(^|/)\.husky/[^/.]+$", rel_norm):
        signals.append(_signal(
            "auto-exec", rel, 1,
            "committed git hook (husky) — runs on git actions after hooks are installed",
        ))
    return signals


def collect_agent_trust_signals(
    root: Path,
    files: list[str],
    *,
    max_signals: int = MAX_SIGNALS,
) -> list[dict]:
    """Run all three signal classes over a repo's tracked/text files."""
    signals: list[dict] = []
    for rel in files:
        if len(signals) >= max_signals:
            signals.append(_signal(
                "truncated", "", 0,
                f"signal cap {max_signals} reached; remaining files not reported",
            ))
            break
        text = _read_text(root / rel)
        if text is None:
            continue
        signals.extend(scan_hidden_unicode(rel, text))
        signals.extend(scan_auto_exec(rel, text))
        if is_agent_instruction_file(rel):
            signals.extend(scan_injection_markers(rel, text))
    return signals[: max_signals + 1]
