---
layout: default
title: Installation
---

# Installation

## From PyPI

```bash
pip install shared-brain
```

## From Source

```bash
git clone https://github.com/yurukusa/shared-brain.git
cd shared-brain
pip install -e .
```

## Claude Code Integration

Register the guard as a PreToolUse hook:

```bash
brain hook install
```

Verify:

```bash
brain hook status
# 🟢 Installed
```

To remove:

```bash
brain hook uninstall
```

## Requirements

- Python 3.8+
- No external dependencies
- PyYAML is optional (used if available, has built-in fallback)
