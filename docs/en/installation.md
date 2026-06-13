# Installing Thanh Tra

> Thanh Tra is a Claude Code skill. Install in two commands.

---

## Table of contents

- [Requirements](#requirements)
- [Install](#install)
- [Verify](#verify)
- [Update](#update)
- [Uninstall](#uninstall)
- [After installation: report location & .gitignore](#after-installation-report-location--gitignore)
- [Troubleshooting](#troubleshooting)
- [Next steps](#next-steps)

---

## Requirements

- **Claude Code** installed (CLI or desktop)
- **A git repository** to scan (Thanh Tra uses `git` to gather the file list per scope)
- **`gh` CLI** (optional) — only needed if you want to scan GitHub PRs via the `pr id <n>` scope

Quick check:

```bash
claude --version
git --version
gh --version        # (Optional) for the pr id scope
```

---

## Install

Run these two commands in your terminal (outside Claude Code):

```bash
git clone https://github.com/aspelldenny/thanhtra ~/thanhtra
ln -sfn ~/thanhtra/skills/thanhtra ~/.claude/skills/thanhtra
```

What each command does:

1. **`git clone`** — downloads the Thanh Tra repository to `~/thanhtra` (you can change the destination if you prefer; just adjust the second command accordingly).

2. **`ln -sfn`** — creates a symlink from `~/.claude/skills/thanhtra` to the skill folder inside the clone. Claude Code auto-discovers anything under `~/.claude/skills/`. Using a symlink (instead of copying) means `git pull` updates the skill in place without having to re-copy.

After running the commands, **restart Claude Code** so it picks up the new skill.

Alternatively, run the installer from the clone — it auto-detects all three platforms (Claude Code, Codex CLI, Antigravity), symlinks the skill for each, and also installs the `thanhtra` CLI (+ `Thanh Tra` alias) into `~/.local/bin`:

```bash
cd ~/thanhtra && ./scripts/install.sh
```

The skill prefers the `thanhtra` CLI on PATH for its deterministic pre-scan (Step 1.5); the script bundled inside the skill is only a fallback. Use `--no-cli` to skip the CLI step.

---

## Verify

After restarting Claude Code, run:

```
/thanhtra
```

If it prints a scan report (header `# Thanh Tra Security Scan Report`), the install succeeded.

You can also confirm the skill is loaded by typing `/` in Claude Code — the autocomplete should list `thanhtra`.

---

## Update

To pull the latest version:

```bash
cd ~/thanhtra
git pull
```

Then restart Claude Code so it reloads the skill from disk.

---

## Uninstall

```bash
rm ~/.claude/skills/thanhtra    # remove the symlink
rm -rf ~/thanhtra                            # remove the source clone (optional)
```

Restart Claude Code.

---

## After installation: report location & .gitignore

When you first run `/thanhtra` in a project repo, Thanh Tra creates `thanhtra-reports/scan-<timestamp>.md` in that repo to persist the report. To prevent committing these scan files, add to your project's `.gitignore`:

```bash
# Add to the scanned project's .gitignore:
echo "thanhtra-reports/" >> .gitignore
git add .gitignore && git commit -m "Add thanhtra-reports/ to .gitignore"
```

> ⚠️ Thanh Tra prints a recommendation at the end of each scan if it detects `thanhtra-reports/` is missing from `.gitignore`. It does **not** automatically modify `.gitignore` — that's your decision.

If you actually want to commit scan reports (e.g., for a compliance trail or PR review evidence), simply don't add the entry. The file naming is timestamped so multiple scans never collide.

---

## Troubleshooting

### `/thanhtra` does not appear in Claude Code

- Confirm the symlink exists: `ls -la ~/.claude/skills/thanhtra` should show a link to `~/thanhtra/skills/thanhtra`.
- Confirm the target exists: `ls ~/thanhtra/skills/thanhtra/SKILL.md` should print a file path.
- Restart Claude Code (close and reopen). Skill discovery runs on startup.

### "Permission denied" on the symlink

Check directory permissions:

```bash
ls -ld ~/.claude/skills
```

If the directory does not exist, create it: `mkdir -p ~/.claude/skills`.

### Multiple Claude Code workspaces

Skills installed in `~/.claude/skills/` are **global** — they apply to every Claude Code workspace you open. No per-workspace install is needed.

### `pr id <n>` scope errors with `command not found: gh`

The PR scope needs the GitHub `gh` CLI:

```bash
# macOS
brew install gh

# Ubuntu/Debian
sudo apt install gh

# Then authenticate
gh auth login
```

Workaround: use a different scope (`uncommitted`, `staged`, `commit id`, `all`).

### Windows / WSL

Native Windows is not officially supported. Use WSL2 with the same instructions above (the symlink and Claude Code's skill discovery both work in WSL).

---

## Next steps

- Read [usage.md](usage.md) for every scope and how to interpret the report
- See [rules.md](rules.md) for the 24 detection rules
- Want to contribute? See [contributing.md](contributing.md)
