---
layout: default
title: Shared Brain
---

# Shared Brain

**AI agents that learn from each other's mistakes — and prove it.**

Shared Brain is a CLI tool that checks commands against structured lessons before execution, logs compliance, and builds audit trails.

## Quick Start

```bash
pip install shared-brain
brain hook install
```

That's it. Every Bash command in Claude Code now gets checked against your lessons.

## Why?

Rules don't work. We wrote "Always GET before PUT" in our instructions. The AI agent ignored it. Twice. Five articles deleted.

Shared Brain turns rules into enforced guardrails:

```
$ brain guard "curl -X PUT https://api.example.com/articles/123"

⚠️  CRITICAL: api-put-safety (violated 2x)
   PUT replaces the ENTIRE resource.

   Checklist:
   [ ] GET the current resource state
   [ ] PUT body contains ALL required fields

Proceed? [y/N]
```

## Features

- **Guard**: Pattern-match commands against YAML lessons
- **Audit**: JSONL trail of every check — who, what, when, followed?
- **Stats**: Compliance rates per lesson, per agent
- **Hook**: One-command Claude Code integration
- **Zero deps**: Pure Python stdlib. No PyYAML needed.

## Links

- [GitHub Repository](https://github.com/yurukusa/shared-brain)
- [Installation Guide](./installation)
- [Tutorial](./tutorial)
- [Writing Lessons](./lessons)
- [API Reference](./api)
- [FAQ](./faq)
- [Troubleshooting](./troubleshooting)
