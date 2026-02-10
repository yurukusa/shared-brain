---
layout: default
title: Tutorial
---

# Tutorial

This guide walks you through using Shared Brain from installation to a fully automated guardrail setup. Every step includes commands you can copy and run.

## Install Shared Brain

### Option A: pip install

```bash
pip install shared-brain
```

This puts the `brain` command on your PATH immediately.

### Option B: Clone from source

```bash
git clone https://github.com/yurukusa/shared-brain.git
cd shared-brain
pip install -e .
```

Or, if you prefer a manual symlink without pip:

```bash
git clone https://github.com/yurukusa/shared-brain.git
cd shared-brain
mkdir -p ~/bin && export PATH=~/bin:$PATH
ln -s $(pwd)/brain ~/bin/brain
```

### Verify the installation

```bash
brain help
```

You should see the list of available commands.

## Explore built-in lessons

Shared Brain ships with 11 lessons covering common AI agent mistakes. See what you have out of the box:

```bash
brain list
```

Output:

```
📚 11 lesson(s):

  🔴 [api-put-safety] CRITICAL — REST PUT replaces the ENTIRE resource...
  🔴 [git-force-push] CRITICAL — Force push, hard reset, and rm -rf...
  🔴 [no-secrets-in-code] CRITICAL — Never commit API keys or passwords...
  ...
```

To see full details on any lesson:

```bash
brain check "api-put-safety"
```

## Create your first lesson

Lessons are YAML files that define what to watch for and what to warn about.

### Interactive mode

The simplest way to add a lesson:

```bash
brain write
```

Follow the prompts. You will be asked for:
- **ID**: A short unique slug (e.g., `check-disk-space`)
- **Severity**: `critical`, `warning`, or `info`
- **Trigger patterns**: Regex patterns that match risky commands
- **Lesson text**: What the agent should know
- **Checklist**: Steps to verify before proceeding

### From a YAML file

Create a file called `my-lesson.yaml`:

```yaml
id: check-disk-space
severity: warning
created: "2026-02-11"
violated_count: 0

trigger_patterns:
  - "docker build"
  - "npm install"
  - "pip install"

lesson: |
  Large installs can fill the disk. Check available space first.
  A full disk causes silent failures and corrupted downloads.

checklist:
  - "Check available disk space (df -h)"
  - "Clean old Docker images if needed (docker system prune)"

tags: [disk, install, docker]
```

Then import it:

```bash
brain write -f my-lesson.yaml
```

Verify it was added:

```bash
brain list
```

Your new lesson now appears alongside the built-in ones.

## Run brain guard

`brain guard` is the core command. It checks a command string against every lesson's trigger patterns.

### Safe command (no match)

```bash
brain guard "ls -la /tmp"
```

No output -- the command is safe. Exit code is `0`.

### Risky command (match found)

```bash
brain guard "curl -X PUT https://api.example.com/articles/123"
```

Output:

```
============================================================
⚠️  CRITICAL LESSON: api-put-safety
   (violated 2x, last: 2026-02-09)
============================================================
   REST PUT replaces the ENTIRE resource. Fields not included in the
   request body will be overwritten with empty/default values.

   Checklist:
   [ ] GET the current resource state
   [ ] PUT body contains ALL required fields
   [ ] Test on 1 item before batch operation
   [ ] Verify result after update

Proceed? [y/N]
```

- Type `y` to acknowledge and proceed. The audit log records `followed: true`.
- Type `n` (or just press Enter) to abort. The audit log records `followed: false`.

### Automation mode

For scripts and hooks, use `--auto-confirm` to skip the interactive prompt:

```bash
brain guard "git push --force" --auto-confirm
```

This still displays the warning and logs the check, but does not block execution.

## Check the audit trail

Every `brain guard` call is recorded in `~/.brain/audit.jsonl`. View the compliance report:

```bash
brain audit
```

Output:

```
📊 Audit Report
==================================================
Total checks: 5
Followed:     4
Blocked:      1
Compliance:   80%

Per-lesson breakdown:
  [api-put-safety] checks=3, followed=2, blocked=1
  [git-force-push] checks=2, followed=2, blocked=0

Last 10 entries:
  ✅ 2026-02-11T14:30:00 [cli-user] curl -X PUT https://api.example.com... (api-put-safety)
  ❌ 2026-02-11T14:28:00 [cli-user] curl -X PUT https://api.example.com... (api-put-safety)
  ...
```

For machine-readable output:

```bash
brain audit --json
```

For a quick summary without the full breakdown:

```bash
brain stats
```

## Install as a Claude Code hook

This is where Shared Brain becomes fully automatic. Instead of manually calling `brain guard`, install it as a PreToolUse hook in Claude Code:

```bash
brain hook install
```

Output:

```
🧠 Brain guard installed into Claude Code!
   Every Bash command will now be checked against lessons.
   Run 'brain hook status' to verify.
```

### What happens after installation

1. Claude Code prepares to execute a Bash command
2. The PreToolUse hook fires automatically
3. `brain guard` checks the command against all lessons
4. If a match is found, the warning is shown to Claude Code
5. If no match, execution proceeds silently

### Verify

```bash
brain hook status
# 🟢 Installed
```

### Uninstall

```bash
brain hook uninstall
# 🗑️  Brain guard hook removed from Claude Code
```

The hook modifies `~/.claude/settings.json`. The install and uninstall commands handle merging with your existing settings safely.

## Set a custom agent name

By default, audit entries are tagged with `cli-user`. To identify different agents:

```bash
export BRAIN_AGENT="my-claude-agent"
brain guard "curl -X PUT https://api.example.com/articles/123"
```

The audit entry will now show `agent: my-claude-agent`, letting you track compliance per agent.

## Export lessons

Share your lessons with teammates or back them up:

```bash
# Markdown format (readable)
brain export --format markdown

# JSON format (machine-readable)
brain export --format json

# Save to a file
brain export --format markdown --output lessons-backup.md
```

## Try the demo

If you want to explore Shared Brain without affecting your real data, use the demo command. It creates a temporary sandbox with pre-loaded lessons and audit data:

```bash
brain demo
```

## Run the benchmark

Curious about performance? Run the benchmark to measure guard latency on your machine:

```bash
brain benchmark
```

Typical results with 100 lessons: P99 latency under 100ms.

## Next steps

- [Writing Lessons](./lessons) -- Full lesson format reference and pattern-matching tips
- [API Reference](./api) -- All commands, environment variables, and exit codes
- [FAQ](./faq) -- Common questions answered
- [Troubleshooting](./troubleshooting) -- When things go wrong
