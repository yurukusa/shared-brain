---
layout: default
title: API Reference
---

# API Reference

## CLI Commands

### `brain list`

Show all lessons.

```bash
brain list
brain list --severity critical
```

### `brain guard <command>`

Check a command against all lessons before execution.

```bash
brain guard "curl -X PUT https://api.example.com/articles/123"
```

Returns exit code 0 if safe or user confirms, 1 if blocked.

### `brain check <keyword>`

Search lessons by keyword.

```bash
brain check "PUT"
brain check "git force"
```

### `brain write`

Add a new lesson interactively, or from a YAML file:

```bash
brain write
brain write -f my-lesson.yaml
```

### `brain audit`

Show compliance report with per-lesson statistics.

```bash
brain audit
brain audit --agent cc-main
```

### `brain stats`

Quick summary of lessons and compliance.

```bash
brain stats
```

### `brain export`

Export lessons in various formats.

```bash
brain export --format markdown
brain export --format json
```

### `brain hook install`

Install brain guard as a Claude Code PreToolUse hook.

```bash
brain hook install
brain hook status    # Check installation
brain hook uninstall # Remove hook
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `BRAIN_HOME` | `~/.brain` | Override brain data directory |
| `BRAIN_AGENT` | hostname | Agent name for audit logging |

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Command is safe / user confirmed |
| 1 | Command blocked by lesson |
| 2 | Warning issued (non-blocking) |
