# Thanh Tra Maintenance

This document describes how to run Thanh Tra as an intermediary security review layer for real repositories, starting with internal projects.

## Goal

Thanh Tra is not a replacement for a professional audit. Its practical role is to:

- Scan repositories before deployment or deeper review.
- Catch common AI-generated code mistakes: leaked secrets, SQL injection, IDOR, race conditions, CORS mistakes, missing rate limits, command injection.
- Produce structured reports that can become remediation tickets.
- Standardize reasoning-based security review instead of simple pattern matching.

## Ownership Principles

The upstream project belongs to its original authors. For internal maintenance:

- Preserve the original license and attribution.
- Contribute generally useful improvements upstream when possible.
- Keep project-specific private rules separate if they reveal sensitive internal details.
- Do not commit scan reports that contain secrets, production paths, or customer data.

## Maintenance Workflow

After changing rules, references, or workflows:

```bash
cd /Users/nguyenhuuanh/code/Thanh Tra

# Run the full local maintenance gate
./scripts/maintain.sh
```

When running each step manually:

```bash
cd /Users/nguyenhuuanh/code/Thanh Tra

# 1. Edit the canonical skill first:
#    skills/thanhtra/...

# 2. Sync shared content to Codex and Antigravity
./scripts/sync-skills.sh

# 3. Validate skill structure
./scripts/validate-skill.sh

# 4. Validate the regression fixture corpus
./scripts/validate-fixtures.sh

# 5. Verify install plan or rely on existing symlinks
./scripts/install.sh --dry-run
```

Do not use a changed build for production repository scans if validation fails.

## Real Repository Scan Workflow

For each project:

```bash
cd /path/to/project

# Full repository scan
$thanhtra all lang=en

# Current local changes
$thanhtra uncommitted lang=en

# Pre-commit scan
$thanhtra staged lang=en
```

After the report:

1. Fix `CRITICAL` findings first.
2. Fix `HIGH` findings before production deployment.
3. Put `MEDIUM` and `LOW` findings into an owned backlog.
4. Re-scan after remediation.
5. If a finding is a clear false positive or false negative, update the canonical rule and rerun the maintenance workflow.

## Suggested Cadence

| Frequency | Task |
|---|---|
| Every skill change | Run `./scripts/maintain.sh` |
| Before major deployment | Run a full `all` scan on the production repository |
| Before sensitive branch merge | Run `uncommitted` or `staged` |
| Weekly | Update dependency/advisory notes for `OUTDATED-DEPENDENCY` |
| Monthly | Review false positives/false negatives from scanned repositories |
| Quarterly | Add fixture tests for new rules and language overlays |

## Next Upgrade Path

Prioritize:

1. Expand fixtures until all 22 rules are covered.
2. Add a machine-readable manifest for rule IDs, severities, and overlays.
3. Integrate supporting scanners such as `gitleaks`, `pnpm audit`, `pip-audit`, `govulncheck`, and `osv-scanner` as evidence providers, not replacements for agent reasoning.
4. Build an internal wrapper that scans multiple repositories and aggregates reports by project.

## Definition of Done for Rule Changes

- Generic rule or overlay has valid frontmatter.
- Unsafe and safe examples are present.
- Reasoning guidance reduces false positives.
- Rule catalog docs are updated when public behavior changes.
- Codex and Antigravity variants are synced.
- `./scripts/validate-skill.sh` passes.
- `./scripts/validate-fixtures.sh` passes.
- At least one small repo or fixture scan was run.
