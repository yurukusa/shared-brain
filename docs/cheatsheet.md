# Shared Brain Cheatsheet

Quick reference for all commands. Print this and keep it handy.

## Core Commands

| Command | Description |
|---------|------------|
| `brain write` | Add a new lesson interactively |
| `brain write -f <file.yaml>` | Import a lesson from YAML file |
| `brain guard "<command>"` | Check command against lessons before running |
| `brain check "<keyword>"` | Search lessons by keyword |
| `brain search "<term>"` | Full-text search with highlighting |
| `brain list` | List all lessons |

## Analysis & Reporting

| Command | Description |
|---------|------------|
| `brain audit` | Show compliance report |
| `brain audit --json` | Export audit data as JSON |
| `brain stats` | Quick stats summary |
| `brain stats --verbose` | Detailed breakdown (categories, top triggers) |

## Search & Filter

| Command | Description |
|---------|------------|
| `brain search "<term>"` | Search lesson text |
| `brain search --tag api` | Filter by tag |
| `brain search --severity critical` | Filter by severity |
| `brain search --tag api "PUT"` | Combine tag filter with keyword |

## Export

| Command | Description |
|---------|------------|
| `brain export` | Export lessons as Markdown (default) |
| `brain export --format json` | Export as JSON |
| `brain export --format html` | Export as standalone HTML |
| `brain export --format md --output file.md` | Export to file |

## Hook Management

| Command | Description |
|---------|------------|
| `brain hook install` | Auto-install guard as Claude Code hook |
| `brain hook uninstall` | Remove the hook |
| `brain hook status` | Check if hook is installed |

## Maintenance

| Command | Description |
|---------|------------|
| `brain doctor` | Run environment diagnostics |
| `brain new` | Generate YAML lesson template |
| `brain uninstall` | Remove hook and audit log |
| `brain uninstall --all` | Remove everything (lessons, plugins too) |
| `brain version` | Show version and system info |

## Learning & Demo

| Command | Description |
|---------|------------|
| `brain tutorial` | Interactive walkthrough (3 steps) |
| `brain demo` | Sandbox with sample data |
| `brain help` | Full help text |

## Environment Variables

| Variable | Description |
|----------|------------|
| `BRAIN_HOME` | Override brain directory (default: `~/.brain`) |
| `BRAIN_AGENT` | Set agent name for audit logging |
| `BRAIN_LANG` | Set language (`en`, `ja`) |

## YAML Lesson Format

```yaml
id: my-lesson-id
severity: critical    # critical | warning | info
created: 2026-02-11
trigger_patterns:
  - "curl.*-X PUT"
  - "rm -rf"
lesson: |
  Explain what agents should know.
  Can be multiline.
checklist:
  - Step 1 to verify
  - Step 2 to verify
tags: [api, safety]
source:
  incident: "What happened that created this lesson"
```

## Quick Start (30 seconds)

```bash
# 1. Install the hook
brain hook install

# 2. See built-in lessons
brain list

# 3. Try the guard
brain guard "curl -X PUT https://api.example.com/data"

# 4. Check the audit
brain audit
```
