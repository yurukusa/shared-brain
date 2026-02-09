# 🧠 Shared Brain

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://img.shields.io/badge/tests-33%20passed-brightgreen.svg)]()
[![No Dependencies](https://img.shields.io/badge/dependencies-none-brightgreen.svg)]()
[![Lessons](https://img.shields.io/badge/built--in%20lessons-11-blue.svg)]()

**AI agents that learn from each other's mistakes — and prove it.**

## Demo

[![asciicast](https://asciinema.org/a/M60qmrt7QscqWVLb.svg)](https://asciinema.org/a/M60qmrt7QscqWVLb)

## The Problem

An AI agent deleted 5 articles by using `PUT` without first doing `GET`. We wrote a lesson: "Always GET before PUT." The next day, the **same agent made the same mistake**. The lesson existed — but nobody checked it.

**Writing lessons is useless if nobody reads them.**

## The Solution

Shared Brain is a CLI tool that:
- **Stores** structured lessons from agent incidents
- **Guards** — automatically warns before risky operations
- **Tracks** — records whether agents checked AND followed lessons
- **Audits** — proves compliance with hard numbers

## Quick Start

```bash
# Install
git clone https://github.com/yurukusa/shared-brain.git
cd shared-brain
ln -s $(pwd)/brain ~/bin/brain

# See what lessons exist
brain list

# Check a command before running it
brain guard "curl -X PUT https://api.example.com/articles/123"

# ⚠️  CRITICAL LESSON: api-put-safety
#    (violated 2x, last: 2026-02-09)
#    "PUT replaces entire resource. Always GET first."
#    Proceed? [y/N]

# Add your own lesson
brain write

# See compliance report
brain audit
```

## Commands

| Command | Description |
|---------|-------------|
| `brain list` | Show all lessons |
| `brain guard <cmd>` | Check command against lessons |
| `brain check <keyword>` | Search lessons by topic |
| `brain write` | Add a new lesson interactively |
| `brain write -f <file>` | Add lesson from YAML file |
| `brain audit` | Compliance report |
| `brain stats` | Quick summary |
| `brain export` | Export lessons (markdown/json) |
| `brain hook install` | Auto-install guard as Claude Code hook |
| `brain hook uninstall` | Remove brain guard hook |
| `brain hook status` | Check if hook is installed |

## How It Works

### Lessons
Stored as YAML files in `~/.brain/lessons/`:

```yaml
id: api-put-safety
severity: critical
trigger_patterns:
  - "PUT /api/"
  - "curl.*-X PUT"
lesson: |
  PUT replaces the entire resource.
  Always GET before PUT.
checklist:
  - "GET the current state"
  - "PUT body contains ALL fields"
```

### Guard
When you run `brain guard`, it matches your command against all lesson `trigger_patterns`. If a match is found, it shows the lesson and asks for confirmation.

### Audit Trail
Every guard check is logged to `~/.brain/audit.jsonl`:
```json
{"timestamp": "2026-02-09T10:30:00Z", "agent": "cc-main", "action": "PUT /api/articles", "checked": true, "followed": true}
```

## Integration

### As a Claude Code Hook
```bash
# One command — auto-installs into ~/.claude/settings.json
brain hook install

# Verify
brain hook status
# 🟢 Installed

# Remove if needed
brain hook uninstall
```

### Environment Variables
- `BRAIN_HOME` — Override brain directory (default: `~/.brain`)
- `BRAIN_AGENT` — Set agent name for audit logging

## Built-in Lessons (Starter Pack)

Ships with 11 lessons covering the most common agent mistakes:

| ID | Severity | What It Catches |
|----|----------|----------------|
| `api-put-safety` | 🔴 Critical | PUT without GET (data loss) |
| `git-force-push` | 🔴 Critical | Force push, hard reset, rm -rf |
| `no-secrets-in-code` | 🔴 Critical | API keys/passwords in commits |
| `no-production-db-direct` | 🔴 Critical | Destructive queries on production DB |
| `dont-delete-without-confirm` | 🔴 Critical | Deleting files/resources without backup |
| `verify-before-claim` | 🟡 Warning | Claiming success without verification |
| `test-before-deploy` | 🟡 Warning | Deploying without running tests |
| `backup-before-migration` | 🟡 Warning | DB migration without backup |
| `check-rate-limits` | 🟡 Warning | Bulk API requests without rate limiting |
| `validate-input-boundaries` | 🟡 Warning | Unsanitized external input |
| `read-error-messages` | ℹ️ Info | Ignoring error messages when debugging |

## The Story Behind This

This tool was born from a real incident: an AI agent (Claude Code) was automating marketing across 11 platforms. On Day 1, it overwrote one Zenn article by using PUT incorrectly. The team wrote a lesson. On Day 2, the **same mistake destroyed all 5 articles**. A reader discovered it.

The lesson existed in a Markdown file. But the agent never checked it before acting. Shared Brain makes sure that can't happen again — not by trusting agents to read docs, but by putting guardrails in their path.

## License

MIT

---

*Built with Claude Code. The same tool that caused the incidents this tool prevents.*
