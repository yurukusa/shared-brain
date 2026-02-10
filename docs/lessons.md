---
layout: default
title: Writing Lessons
---

# Writing Lessons

## Lesson Format

Lessons are YAML files stored in `~/.brain/lessons/`.

```yaml
id: my-lesson-id
severity: critical    # critical | warning | info
created: "2026-02-10"
violated_count: 0

trigger_patterns:
  - "regex pattern 1"
  - "regex pattern 2"

lesson: |
  What went wrong and why.
  What to do instead.

checklist:
  - "Step 1 to verify"
  - "Step 2 to verify"

source:
  incident: "Description of what happened"

tags: [relevant, tags]
```

## Adding Lessons

### From a YAML file

```bash
brain write -f my-lesson.yaml
```

### Interactively

```bash
brain write
# Follow the prompts
```

## Built-in Lessons

Shared Brain ships with 18 lessons covering common agent mistakes:

| ID | Severity | Prevents |
|----|----------|----------|
| `api-put-safety` | critical | Data loss from PUT without GET |
| `git-force-push` | critical | Force push, hard reset, rm -rf |
| `no-secrets-in-code` | critical | API keys in source code |
| `verify-before-claim` | warning | Claiming success without verification |
| `test-before-deploy` | warning | Deploying without tests |

See `lessons/` in the repository for the full list.

## Pattern Matching

Trigger patterns are matched using Python `re.search()` with `re.IGNORECASE`.

If a pattern has invalid regex syntax, it falls back to substring matching.

Tips:
- Use `\\b` for word boundaries: `"\\brm -rf\\b"`
- Escape special characters: `"requests\\.put"`
- Keep patterns specific to avoid false positives
