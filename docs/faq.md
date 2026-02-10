---
layout: default
title: FAQ
---

# Frequently Asked Questions

## What is Shared Brain?

Shared Brain is a CLI tool that stores structured lessons from AI agent incidents and enforces them as guardrails before risky operations. Every check is logged to an audit trail so you can prove whether agents actually read and followed the lessons.

It was born from a real incident: an AI agent destroyed 5 Zenn articles by using `PUT` without first doing `GET`. The lesson "Always GET before PUT" existed in a Markdown file, but the agent never checked it before acting. Shared Brain makes sure that cannot happen again.

## How is it different from linters or static analysis?

Linters check code syntax and style. Shared Brain checks **intent** -- it matches commands against lessons learned from past incidents.

Key differences:

| | Linters | Shared Brain |
|---|---------|-------------|
| **What it checks** | Code syntax and style | Commands and operations |
| **Rule source** | Language specification | Team-specific incidents |
| **When it runs** | On code files | Before command execution |
| **Audit trail** | No | Yes -- logs every check with agent, timestamp, and compliance |
| **Grows from** | Language updates | Your team's real mistakes |

Think of it as institutional memory with enforcement, not code quality tooling.

## Does brain guard block commands?

By default, `brain guard` is **advisory**. When a match is found, it displays the lesson and asks for confirmation:

```
Proceed? [y/N]
```

- If you answer `y`, the command proceeds and the audit records `followed: true`.
- If you answer `n` (or press Enter), the command is aborted and the audit records `followed: false`.

When installed as a Claude Code hook, the behavior depends on the hook type. As a PreToolUse hook, brain guard displays warnings that Claude Code can see and act on.

The `--auto-confirm` flag skips the prompt entirely while still logging the check. This is useful in scripts where blocking is not desired.

## What happens if PyYAML is not installed?

Shared Brain works without any external dependencies. It includes a built-in minimal YAML parser that handles the lesson file format (key-value pairs, lists, multiline strings, and inline lists).

**With PyYAML**: Full YAML spec support, handles edge cases in complex lesson files.

**Without PyYAML**: Built-in parser covers the lesson format. You will not notice a difference for standard lessons. Edge cases with deeply nested YAML or unusual syntax may not parse correctly.

To install PyYAML as an optional enhancement:

```bash
pip install pyyaml
```

## Can I share lessons between teams?

Yes. Lessons are plain YAML files stored in `~/.brain/lessons/`. You can share them in several ways:

**Git repository**: Keep your lessons in a shared repo and sync them across machines:

```bash
# On machine A
cp ~/.brain/lessons/my-lesson.yaml /path/to/shared-repo/lessons/
cd /path/to/shared-repo && git add . && git commit -m "Add lesson" && git push

# On machine B
cd /path/to/shared-repo && git pull
cp lessons/*.yaml ~/.brain/lessons/
```

**Export and import**: Use the export command to share lessons as Markdown or JSON:

```bash
brain export --format json --output team-lessons.json
```

**Custom BRAIN_HOME**: Point multiple agents at a shared directory:

```bash
export BRAIN_HOME=/shared/team-brain
brain list  # All agents see the same lessons
```

**Post-hackathon roadmap**: A `brain sync` command for native team sharing is planned.

## How fast is brain guard?

Fast enough that you will not notice it. Benchmarks with 100 lessons loaded:

| Metric | Value |
|--------|-------|
| Mean latency | 76ms |
| Median latency | 75ms |
| P95 latency | 86ms |
| P99 latency | 93ms |

Guard latency scales linearly with the number of lessons. With 10 lessons (a typical setup), it runs in under 20ms.

Run the benchmark on your own machine:

```bash
brain benchmark
```

## What is the lesson format?

Lessons are YAML files with this structure:

```yaml
id: my-lesson-id              # Unique identifier (required)
severity: critical             # critical | warning | info (required)
created: "2026-02-11"         # Date created
violated_count: 0              # How many times this was violated

trigger_patterns:              # Regex patterns to match (required)
  - "curl.*-X PUT"
  - "requests\\.put"

lesson: |                      # What happened and what to do (required)
  Explain the risk clearly.
  Include what to do instead.

checklist:                     # Steps to verify before proceeding
  - "Step 1"
  - "Step 2"

source:                        # Where this lesson came from
  incident: "Brief description"
  url: "https://example.com"

tags: [api, safety]            # For search and filtering
```

**Required fields**: `id`, `severity`, `trigger_patterns`, `lesson`.

**Trigger patterns** use Python regex with `re.IGNORECASE`. If a pattern has invalid regex syntax, it falls back to case-insensitive substring matching.

See the [Writing Lessons](./lessons) page for the full reference and pattern-matching tips.

## How do I reset audit data?

The audit trail is stored in `~/.brain/audit.jsonl`, one JSON object per line.

**Reset everything**:

```bash
rm ~/.brain/audit.jsonl
```

The next `brain guard` call will create a fresh file.

**Reset selectively**: Since it is a plain text file (JSONL format), you can filter entries with standard tools:

```bash
# Keep only entries from the last 7 days
python3 -c "
import json, datetime
cutoff = (datetime.datetime.now() - datetime.timedelta(days=7)).isoformat()
with open('$HOME/.brain/audit.jsonl') as f:
    entries = [line for line in f if json.loads(line).get('timestamp','') > cutoff]
with open('$HOME/.brain/audit.jsonl', 'w') as f:
    f.writelines(entries)
"
```

**Back up before resetting**:

```bash
cp ~/.brain/audit.jsonl ~/.brain/audit.jsonl.bak
```

## Can I use brain guard outside of Claude Code?

Yes. Brain guard is a standalone CLI command. You can use it:

**In shell scripts**:

```bash
brain guard "rm -rf /var/data" && rm -rf /var/data
```

**As a git pre-commit hook**:

```bash
#!/bin/bash
brain guard "git commit" || exit 1
```

**As a shell alias**:

```bash
alias curl='brain guard curl'
```

**In CI/CD pipelines**:

```bash
brain guard "$DEPLOY_COMMAND" --auto-confirm
```

## How many lessons can I have?

There is no hard limit. Performance with 100 lessons is well under 100ms per guard check. At 1,000 lessons you may see latency around 500-700ms per check. For most teams, 10-30 lessons covers the critical scenarios.

## Where is data stored?

All data lives under `~/.brain/` (configurable via `BRAIN_HOME`):

```
~/.brain/
  lessons/       # Your custom lessons (YAML files)
  audit.jsonl    # Audit trail (one JSON object per line)
  audit/         # Reserved for future audit partitioning
```

Built-in lessons ship with the source code in the `lessons/` directory of the repository and are loaded alongside your custom ones. Custom lessons with the same `id` as a built-in lesson take precedence.
