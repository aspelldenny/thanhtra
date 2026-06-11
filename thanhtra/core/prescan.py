#!/usr/bin/env python3
"""Deterministic evidence collector for Thanh Tra.

This script gives the LLM stable "eyes and hands" before reasoning:
- inventory files and language counts
- collect security hot spots mapped to the 22 canonical rule IDs
- mask possible secrets
- collect git-history secret signals without printing secret values
- run dependency audit tools when already available

It does not decide final vulnerabilities. The agent must still read context and
apply L1-L4 reasoning from the skill rules.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


VENDORED_PARTS = {
    ".git",
    ".next",
    ".nuxt",
    ".venv",
    "node_modules",
    "vendor",
    "dist",
    "build",
    "target",
    "__pycache__",
    "thanhtra-reports",
}

TEXT_SUFFIXES = {
    ".py", ".pyw", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs",
    ".go", ".php", ".phtml", ".rb", ".java", ".rs", ".cs", ".kt", ".kts",
    ".json", ".yaml", ".yml", ".toml", ".env", ".ini", ".cfg", ".conf",
    ".sh", ".bash", ".zsh", ".sql", ".md", ".txt", ".dockerfile",
}

DOC_SUFFIXES = {".md", ".mdx", ".rst", ".adoc", ".txt"}
CONFIG_SUFFIXES = {".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf"}
SCRIPT_SUFFIXES = {".sh", ".bash", ".zsh", ".sql"}

LANG_EXTS = {
    "python": {".py", ".pyw"},
    "typescript": {".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"},
    "go": {".go"},
    "php": {".php", ".phtml"},
    "ruby": {".rb"},
    "java": {".java"},
    "rust": {".rs"},
    "csharp": {".cs"},
    "kotlin": {".kt", ".kts"},
}

SOURCE_SUFFIXES = set().union(*LANG_EXTS.values())

DEPENDENCY_FILES = {
    "package.json", "package-lock.json", "pnpm-lock.yaml", "yarn.lock",
    "requirements.txt", "pyproject.toml", "poetry.lock", "Pipfile.lock",
    "go.mod", "go.sum", "composer.json", "composer.lock", "Gemfile.lock",
    "Cargo.toml", "Cargo.lock",
}

SECRET_PATTERNS = [
    ("HARDCODED-SECRET", "anthropic", re.compile(r"sk-ant-[A-Za-z0-9_\-]{40,}")),
    ("HARDCODED-SECRET", "openai", re.compile(r"sk-[A-Za-z0-9]{48}")),
    ("HARDCODED-SECRET", "aws", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("HARDCODED-SECRET", "github-pat", re.compile(r"gh[pous]_[A-Za-z0-9]{36}")),
    ("HARDCODED-SECRET", "google-api", re.compile(r"AIza[0-9A-Za-z_\-]{35}")),
    ("HARDCODED-SECRET", "telegram-bot", re.compile(r"\b\d{8,12}:[A-Za-z0-9_\-]{35}\b")),
    ("HARDCODED-SECRET", "stripe", re.compile(r"sk_(live|test)_[A-Za-z0-9]{24,}")),
    ("HARDCODED-SECRET", "slack", re.compile(r"xox[baprs]-[A-Za-z0-9\-]{10,}")),
    (
        "HARDCODED-SECRET",
        "generic-secret-assignment",
        re.compile(
            r"(?i)(api[_-]?key|apikey|secret|password|passwd|token|jwt[_-]?secret|private[_-]?key)"
            r"\s*[:=]\s*['\"]([A-Za-z0-9_\-+/=]{24,})['\"]"
        ),
    ),
]

HOTSPOT_PATTERNS = {
    "SQL-INJECTION": [
        r"execute\s*\(\s*f[\"']",
        r"execute\s*\(\s*[\"'][^\"']*[\"']\s*%",
        r"execute\s*\(\s*[\"'][^\"']*[\"']\s*\+",
        r"text\s*\(\s*f[\"']",
        r"\.raw\s*\(\s*f[\"']",
        r"\.query\s*\(\s*`[^`]*\$\{",
        r"db\.(Query|Exec|QueryRow)\s*\(\s*fmt\.Sprintf",
    ],
    "XSS": [
        r"dangerouslySetInnerHTML",
        r"v-html\s*=",
        r"\.innerHTML\s*=",
        r"document\.write\s*\(",
        r"\|\s*safe\b",
        r"Html\.Raw\s*\(",
    ],
    "IDOR": [
        r"findById\s*\(\s*req\.(params|body|query)",
        r"Model\.objects\.get\s*\(\s*id\s*=",
        r"SELECT .* WHERE id\s*=",
        r"router\.(get|put|patch|delete)\s*\([^)]*:id",
    ],
    "SLOPSQUATTING": [
        r"^\s*import\s+[A-Za-z_][A-Za-z0-9_]*",
        r"^\s*from\s+[A-Za-z_][A-Za-z0-9_]*\s+import",
        r"^\s*import .* from [\"'][^\"'./][^\"']*[\"']",
        r"require\s*\(\s*[\"'][^\"'./][^\"']*[\"']\s*\)",
    ],
    "BRUTE-FORCE": [
        r"(login|signin|auth|password|otp|2fa|reset)",
    ],
    "MASS-ASSIGNMENT": [
        r"\*\*request\.",
        r"fields\s*=\s*[\"']__all__[\"']",
        r"extra\s*=\s*[\"']allow[\"']",
        r"setattr\s*\([^,]+,\s*\w+",
        r"\.update\s*\(\s*\*\*",
    ],
    "INSECURE-DESERIALIZATION": [
        r"pickle\.loads?\s*\(",
        r"yaml\.load\s*\(",
        r"marshal\.loads?\s*\(",
        r"jsonpickle\.decode\s*\(",
        r"\beval\s*\(",
        r"\bexec\s*\(",
    ],
    "SSRF": [
        r"requests\.(get|post|put|delete|request)\s*\(",
        r"httpx\.(get|post|request|AsyncClient)",
        r"fetch\s*\(",
        r"axios\.(get|post|request)\s*\(",
        r"urlopen\s*\(",
    ],
    "PATH-TRAVERSAL": [
        r"open\s*\([^)]*(request|req\.|params|query|body)",
        r"send_file\s*\(",
        r"send_from_directory\s*\(",
        r"fs\.(readFile|writeFile|createReadStream)\s*\(",
        r"\.\./",
    ],
    "CSRF": [
        r"csrf_exempt",
        r"WTF_CSRF_ENABLED\s*=\s*False",
        r"csrf\s*:\s*false",
        r"SameSite=None",
    ],
    "BROKEN-ACCESS-CONTROL": [
        r"(admin|delete|update|role|permission|tenant|owner|user_id)",
        r"ports\s*:",
        r"\d+\.\d+\.\d+\.\d+:\d+:\d+",
    ],
    "WEAK-PASSWORD-HASHING": [
        r"hashlib\.(md5|sha1|sha256|sha512)\s*\(",
        r"crypto\.createHash\s*\(\s*[\"'](md5|sha1|sha256|sha512)[\"']",
        r"\bmd5\s*\(",
        r"password\s*==",
    ],
    "JWT-NONE-ALGORITHM": [
        r"jwt\.decode\s*\(",
        r"algorithms\s*=\s*\[[^\]]*[\"']none[\"']",
        r"verify_signature\s*:\s*False",
    ],
    "CORS-MISCONFIG": [
        r"allow_origins\s*=\s*\[\s*[\"']\*[\"']",
        r"CORS_ALLOW_ALL_ORIGINS\s*=\s*True",
        r"Access-Control-Allow-Origin.*\*",
        r"cors\s*\(\s*\)",
    ],
    "UNRESTRICTED-FILE-UPLOAD": [
        r"request\.files",
        r"req\.file",
        r"multer\s*\(",
        r"move_uploaded_file\s*\(",
        r"\.save\s*\(",
        r"upload",
    ],
    "VERBOSE-ERROR-DEBUG-MODE": [
        r"debug\s*=\s*True",
        r"DEBUG\s*=\s*True",
        r"FastAPI\s*\([^)]*debug\s*=\s*True",
        r"traceback\.format_exc\s*\(",
        r"err\.stack",
        r"breakpoint\s*\(",
        r"set_trace\s*\(",
    ],
    "MISSING-RATE-LIMIT": [
        r"(login|signin|otp|password|reset|upload|webhook)",
    ],
    "RACE-CONDITION": [
        r"(balance|wallet|credit|stock|inventory|quota|coupon|water_ml)",
        r"SELECT .* FOR UPDATE",
        r"\.transaction\s*\(",
        r"\+=|-=|=\s*.*\+",
    ],
    "OUTDATED-DEPENDENCY": [
        r"^(fastapi|starlette|python-dotenv|django|flask|requests|pyyaml|urllib3|jinja2|werkzeug)==",
        r"\"(lodash|jquery|axios|next|express)\"",
    ],
    "COMMAND-INJECTION": [
        r"subprocess\.(run|call|Popen|check_output|check_call)\s*\(",
        r"shell\s*=\s*True",
        r"os\.system\s*\(",
        r"os\.popen\s*\(",
        r"child_process\.exec\s*\(",
        r"exec\.Command\s*\(\s*[\"'](sh|bash|cmd)",
    ],
    "PROMPT-INJECTION": [
        r"(system_prompt|system_message|instructions?)\s*\+",
        r"(system_prompt|system_message|system|instructions?)\s*=\s*f[\"']",
        r"role\s*[:=]\s*[\"']system[\"']",
        r"\.(chat|messages|responses|completions)\.(create|completions)\s*\(",
        r"\b(ChatCompletion|generate_content|invoke)\s*\(",
        r"\btools\s*=\s*\[",
        r"\b(tool_calls|function_call|tool_use)\b",
        r"(similarity_search|as_retriever|vector_?store)",
        r"(user_knowledge|user_facts|user_memory|memory)\b.*\b(insert|update|upsert|save|store)\b",
    ],
}


def run(cmd: list[str], cwd: Path, timeout: int = 20) -> tuple[int, str, str]:
    try:
        p = subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, timeout=timeout)
        return p.returncode, p.stdout, p.stderr
    except Exception as exc:  # noqa: BLE001
        return 127, "", str(exc)


# Artifact do chính Thanh Tra sinh ra — scan lại sẽ tạo feedback loop (hotspot rác,
# fingerprint đổi giữa các lần chạy).
TOOL_ARTIFACT_NAMES = {".thanhtra-pre-scan.json", ".vbsec-pre-scan.json", ".anhsec-pre-scan.json"}
TOOL_ARTIFACT_DIRS = {
    "thanhtra-reports", "vbsec-reports", "anhsec-reports",
    ".thanhtra-tmp", ".vbsec-tmp",
}


def is_tool_artifact(path: Path) -> bool:
    if path.name in TOOL_ARTIFACT_NAMES:
        return True
    return any(part in TOOL_ARTIFACT_DIRS for part in path.parts)


def is_vendored(path: Path) -> bool:
    if is_tool_artifact(path):
        return True
    return any(part in VENDORED_PARTS for part in path.parts)


def is_text_candidate(path: Path) -> bool:
    if path.name in DEPENDENCY_FILES or path.name.startswith(".env"):
        return True
    suffix = path.suffix.lower()
    return suffix in TEXT_SUFFIXES or path.name in {"Dockerfile", ".gitignore", ".htaccess"}


def classify_file(rel: str) -> str:
    path = Path(rel)
    name = path.name
    suffix = path.suffix.lower()
    parts = set(path.parts)
    if name in DEPENDENCY_FILES:
        return "dependency"
    if name.startswith(".env"):
        return "secret-config"
    if name in {"Dockerfile", ".dockerignore"} or name.startswith("docker-compose"):
        return "deploy-config"
    if ".github" in parts or name in {".gitignore", ".htaccess"}:
        return "repo-config"
    if suffix in SOURCE_SUFFIXES:
        return "source"
    if suffix in SCRIPT_SUFFIXES:
        return "script"
    if suffix in CONFIG_SUFFIXES:
        return "config"
    if suffix in DOC_SUFFIXES or "docs" in parts:
        return "documentation"
    return "other"


def file_kind_counts(files: Iterable[str]) -> dict[str, int]:
    return dict(Counter(classify_file(f) for f in files))


def is_hotspot_candidate(rel: str) -> bool:
    return classify_file(rel) in {"source", "script", "config"}


def mask(value: str) -> str:
    if len(value) <= 12:
        return "***" + value[-4:]
    return f"{value[:4]}...{value[-4:]}"


def safe_line(line: str) -> str:
    out = line.strip()
    for _, _, pattern in SECRET_PATTERNS:
        out = pattern.sub(lambda m: m.group(0).replace(m.group(0), mask(m.group(0))), out)
    return out[:300]


def collect_files(root: Path) -> tuple[bool, list[str]]:
    rc, out, _ = run(["git", "rev-parse", "--is-inside-work-tree"], root, timeout=5)
    is_git = rc == 0 and out.strip() == "true"
    if is_git:
        # --others --exclude-standard: vibe code thường có file chưa commit; vẫn phải scan.
        rc, out, _ = run(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard"], root, timeout=10
        )
        files = [line for line in out.splitlines() if line and not is_vendored(Path(line))]
        return True, sorted(files)
    files = []
    for p in root.rglob("*"):
        if p.is_file():
            rel = p.relative_to(root)
            if not is_vendored(rel):
                files.append(str(rel))
    return False, sorted(files)


def language_counts(files: Iterable[str]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for f in files:
        suffix = Path(f).suffix.lower()
        for lang, exts in LANG_EXTS.items():
            if suffix in exts:
                counts[lang] += 1
                break
    return dict(counts)


def read_lines(path: Path) -> list[str]:
    try:
        return path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except OSError:
        return []


def collect_hotspots(root: Path, files: list[str], max_per_rule: int) -> dict[str, list[dict]]:
    compiled = {
        rule: [re.compile(p, re.IGNORECASE) for p in patterns]
        for rule, patterns in HOTSPOT_PATTERNS.items()
    }
    findings: dict[str, list[dict]] = defaultdict(list)
    for rel in files:
        path = root / rel
        if not is_text_candidate(path) or not is_hotspot_candidate(rel):
            continue
        lines = read_lines(path)
        if not lines or len(lines) > 8000:
            continue
        for lineno, line in enumerate(lines, 1):
            for rule, patterns in compiled.items():
                if len(findings[rule]) >= max_per_rule:
                    continue
                for pattern in patterns:
                    if pattern.search(line):
                        findings[rule].append({
                            "path": rel,
                            "line": lineno,
                            "pattern": pattern.pattern,
                            "snippet": safe_line(line),
                        })
                        break
    return dict(findings)


def collect_secret_hits(root: Path, files: list[str], max_hits: int) -> list[dict]:
    hits: list[dict] = []
    for rel in files:
        path = root / rel
        if not is_text_candidate(path):
            continue
        for lineno, line in enumerate(read_lines(path), 1):
            for rule_id, name, pattern in SECRET_PATTERNS:
                if len(hits) >= max_hits:
                    return hits
                for m in pattern.finditer(line):
                    hits.append({
                        "rule_id": rule_id,
                        "type": name,
                        "path": rel,
                        "line": lineno,
                        "masked": mask(m.group(0)),
                        "snippet": safe_line(line),
                    })
    return hits


def collect_git_secret_signals(root: Path, is_git: bool) -> list[dict]:
    if not is_git:
        return []
    rc, out, err = run(
        ["git", "log", "--all", "--pretty=format:%h %ad %s", "--date=short", "--grep=secret\\|token\\|password\\|PAT\\|credential", "-i"],
        root,
        timeout=10,
    )
    signals = []
    if rc == 0:
        for line in out.splitlines()[:50]:
            signals.append({"kind": "commit-message", "summary": line})
    elif err:
        signals.append({"kind": "git-error", "summary": err[:300]})
    rc, out, _ = run(["git", "log", "--all", "--pretty=format:", "--name-only"], root, timeout=15)
    if rc == 0:
        names = sorted(set(x for x in out.splitlines() if x))
        for name in names:
            if re.search(r"(^|/)(\.env($|\.)|.*secret.*|.*credential.*|.*token.*|.*\.pem$|.*\.p12$|.*\.pfx$)", name, re.I):
                signals.append({"kind": "history-path", "path": name})
                if len(signals) >= 100:
                    break
    return signals


def collect_dependency_files(root: Path, files: list[str]) -> list[str]:
    return [f for f in files if Path(f).name in DEPENDENCY_FILES]


def audit_dependencies(root: Path, dep_files: list[str]) -> list[dict]:
    audits = []
    if "requirements.txt" in dep_files:
        if shutil.which("pip-audit"):
            rc, out, err = run(["pip-audit", "-r", "requirements.txt"], root, timeout=90)
            audits.append({
                "tool": "pip-audit",
                "rc": rc,
                "stdout": out[:8000],
                "stderr": err[:2000],
                "vulnerabilities": parse_pip_audit(out),
            })
        else:
            audits.append({"tool": "pip-audit", "status": "missing"})
    if "package-lock.json" in dep_files or "package.json" in dep_files:
        if shutil.which("npm"):
            rc, out, err = run(["npm", "audit", "--json"], root, timeout=90)
            audits.append({
                "tool": "npm audit",
                "rc": rc,
                "stdout": out[:12000],
                "stderr": err[:2000],
                "vulnerabilities": parse_npm_audit(out),
            })
        else:
            audits.append({"tool": "npm audit", "status": "missing"})
    if "pnpm-lock.yaml" in dep_files:
        if shutil.which("pnpm"):
            rc, out, err = run(["pnpm", "audit", "--json"], root, timeout=90)
            audits.append({
                "tool": "pnpm audit",
                "rc": rc,
                "stdout": out[:12000],
                "stderr": err[:2000],
                "vulnerabilities": parse_pnpm_audit(out),
            })
        else:
            audits.append({"tool": "pnpm audit", "status": "missing"})
    if "Cargo.lock" in dep_files:
        if shutil.which("cargo-audit") or shutil.which("cargo"):
            rc, out, err = run(["cargo", "audit", "--json"], root, timeout=120)
            audits.append({
                "tool": "cargo audit",
                "rc": rc,
                "stdout": out[:12000],
                "stderr": err[:2000],
                "vulnerabilities": parse_cargo_audit(out),
                "warnings": parse_cargo_audit_warnings(out),
            })
        else:
            audits.append({"tool": "cargo audit", "status": "missing"})
    return audits


def parse_pip_audit(output: str) -> list[dict]:
    vulns = []
    seen = set()
    for line in output.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(("Found ", "Name ", "-----")):
            continue
        parts = stripped.split()
        if len(parts) < 4:
            continue
        name, version, advisory = parts[:3]
        fix_versions = " ".join(parts[3:])
        entry = {
            "package": name,
            "version": version,
            "advisory": advisory,
            "fix_versions": [v.strip(",") for v in fix_versions.split(",") if v.strip(",")],
            "source": "pip-audit",
        }
        key = (entry["package"], entry["version"], entry["advisory"], tuple(entry["fix_versions"]))
        if key in seen:
            continue
        seen.add(key)
        vulns.append(entry)
    return vulns


def parse_npm_audit(output: str) -> list[dict]:
    try:
        data = json.loads(output)
    except json.JSONDecodeError:
        return []
    vulns = []
    for name, item in (data.get("vulnerabilities") or {}).items():
        via_items = item.get("via") or []
        advisories = []
        for via in via_items:
            if isinstance(via, dict):
                advisories.append(str(via.get("source") or via.get("url") or via.get("title") or "unknown"))
            elif isinstance(via, str):
                advisories.append(via)
        vulns.append({
            "package": name,
            "version": item.get("range") or "",
            "severity": item.get("severity"),
            "advisories": advisories,
            "fix_available": item.get("fixAvailable"),
            "source": "npm audit",
        })
    return vulns


def parse_pnpm_audit(output: str) -> list[dict]:
    try:
        data = json.loads(output)
    except json.JSONDecodeError:
        return []
    vulns = []
    advisories = data.get("advisories") or {}
    for advisory_id, item in advisories.items():
        vulns.append({
            "package": item.get("module_name"),
            "version": item.get("vulnerable_versions") or "",
            "severity": item.get("severity"),
            "advisory": str(item.get("cves") or advisory_id),
            "fix_versions": [item["patched_versions"]] if item.get("patched_versions") else [],
            "source": "pnpm audit",
        })
    return vulns


def parse_cargo_audit(output: str) -> list[dict]:
    try:
        data = json.loads(output)
    except json.JSONDecodeError:
        return []
    vulns = []
    entries = ((data.get("vulnerabilities") or {}).get("list") or [])
    for item in entries:
        advisory = item.get("advisory") or {}
        package = item.get("package") or {}
        versions = item.get("versions") or {}
        vulns.append({
            "package": package.get("name") or advisory.get("package"),
            "version": str(package.get("version") or ""),
            "severity": advisory.get("cvss"),
            "advisory": advisory.get("id"),
            "aliases": advisory.get("aliases") or [],
            "title": advisory.get("title"),
            "url": advisory.get("url"),
            "fix_versions": versions.get("patched") or [],
            "source": "cargo audit",
        })
    return vulns


def parse_cargo_audit_warnings(output: str) -> list[dict]:
    try:
        data = json.loads(output)
    except json.JSONDecodeError:
        return []
    warnings = []
    for kind, items in (data.get("warnings") or {}).items():
        for item in items or []:
            advisory = item.get("advisory") or {}
            package = item.get("package") or {}
            warnings.append({
                "kind": kind,
                "package": package.get("name") or advisory.get("package"),
                "version": str(package.get("version") or ""),
                "advisory": advisory.get("id"),
                "title": advisory.get("title"),
                "url": advisory.get("url"),
                "source": "cargo audit",
            })
    return warnings


def dependency_audit_gaps(dep_files: list[str], audits: list[dict]) -> list[str]:
    gaps = []
    if "Cargo.toml" in dep_files and "Cargo.lock" not in dep_files:
        gaps.append("Cargo.toml present but Cargo.lock missing; cargo audit needs a lockfile for deterministic Rust advisory scan.")
    for audit in audits:
        tool = audit.get("tool") or "dependency audit"
        status = audit.get("status")
        if status == "missing":
            gaps.append(f"{tool} missing; install the tool to scan matching dependency files.")
            continue
        rc = audit.get("rc")
        stdout = audit.get("stdout") or ""
        stderr = audit.get("stderr") or ""
        has_vulns = bool(audit.get("vulnerabilities"))
        if rc not in (None, 0) and not has_vulns:
            detail = (stderr or stdout).strip().splitlines()
            suffix = f": {detail[0][:240]}" if detail else ""
            gaps.append(f"{tool} failed with rc={rc}{suffix}")
    return gaps


def docker_exposures(root: Path, files: list[str]) -> list[dict]:
    exposures = []
    for rel in files:
        if not (Path(rel).name.startswith("docker-compose") and Path(rel).suffix in {".yml", ".yaml"}):
            continue
        for lineno, line in enumerate(read_lines(root / rel), 1):
            if re.search(r"['\"]?\d+:\d+['\"]?", line) and "127.0.0.1:" not in line:
                exposures.append({"path": rel, "line": lineno, "snippet": line.strip()})
    return exposures


def tool_availability() -> dict[str, bool]:
    return {
        "git": shutil.which("git") is not None,
        "pip-audit": shutil.which("pip-audit") is not None,
        "npm": shutil.which("npm") is not None,
        "pnpm": shutil.which("pnpm") is not None,
        "cargo-audit": (shutil.which("cargo-audit") is not None or shutil.which("cargo") is not None and "audit" in cargo_subcommands()),
    }


def cargo_subcommands() -> str:
    if not shutil.which("cargo"):
        return ""
    rc, out, _err = run(["cargo", "--list"], Path.cwd(), timeout=15)
    if rc != 0:
        return ""
    return out


def evidence_fingerprint(evidence: dict) -> str:
    stable = {
        "schema": evidence.get("schema"),
        "root": evidence.get("root"),
        "is_git_repo": evidence.get("is_git_repo"),
        "file_count": evidence.get("file_count"),
        "file_kind_counts": evidence.get("file_kind_counts"),
        "hotspot_file_count": evidence.get("hotspot_file_count"),
        "language_counts": evidence.get("language_counts"),
        "dependency_files": evidence.get("dependency_files"),
        "secret_hits_masked": evidence.get("secret_hits_masked"),
        "git_secret_signals": evidence.get("git_secret_signals"),
        "docker_exposures": evidence.get("docker_exposures"),
        "hotspots_by_rule": evidence.get("hotspots_by_rule"),
        "dependency_audits": evidence.get("dependency_audits"),
        "dependency_vulnerabilities": evidence.get("dependency_vulnerabilities"),
        "dependency_warnings": evidence.get("dependency_warnings"),
        "audit_gaps": evidence.get("audit_gaps"),
    }
    payload = json.dumps(stable, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_evidence(
    root: Path,
    *,
    max_per_rule: int = 80,
    max_secrets: int = 100,
    no_audit: bool = False,
) -> dict:
    root = root.resolve()
    is_git, files = collect_files(root)
    dep_files = collect_dependency_files(root, files)
    hotspot_files = [f for f in files if is_hotspot_candidate(f)]
    dependency_audits = [] if no_audit else audit_dependencies(root, dep_files)
    dependency_vulnerabilities = [
        vuln
        for audit in dependency_audits
        for vuln in audit.get("vulnerabilities", [])
    ]
    dependency_warnings = [
        warning
        for audit in dependency_audits
        for warning in audit.get("warnings", [])
    ]
    audit_gaps = [] if no_audit else dependency_audit_gaps(dep_files, dependency_audits)
    evidence = {
        "schema": "thanhtra-pre-scan/v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "root": str(root),
        "is_git_repo": is_git,
        "tool_availability": tool_availability(),
        "file_count": len(files),
        "file_kind_counts": file_kind_counts(files),
        "hotspot_file_count": len(hotspot_files),
        "language_counts": language_counts(files),
        "dependency_files": dep_files,
        "secret_hits_masked": collect_secret_hits(root, files, max_secrets),
        "git_secret_signals": collect_git_secret_signals(root, is_git),
        "docker_exposures": docker_exposures(root, files),
        "hotspots_by_rule": collect_hotspots(root, files, max_per_rule),
        "dependency_audits": dependency_audits,
        "dependency_vulnerabilities": dependency_vulnerabilities,
        "dependency_warnings": dependency_warnings,
        "audit_gaps": audit_gaps,
    }
    evidence["fingerprint_sha256"] = evidence_fingerprint(evidence)
    return evidence


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".", help="repo/folder root to scan")
    parser.add_argument("--output", help="write JSON evidence to this path instead of stdout")
    parser.add_argument("--max-per-rule", type=int, default=80)
    parser.add_argument("--max-secrets", type=int, default=100)
    parser.add_argument("--no-audit", action="store_true", help="skip dependency audit commands")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    evidence = build_evidence(
        root,
        max_per_rule=args.max_per_rule,
        max_secrets=args.max_secrets,
        no_audit=args.no_audit,
    )
    output = json.dumps(evidence, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        output_path = Path(args.output)
        if not output_path.is_absolute():
            output_path = root / output_path
        output_path.write_text(output, encoding="utf-8")
    else:
        sys.stdout.write(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
