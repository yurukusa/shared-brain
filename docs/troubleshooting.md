---
layout: default
title: Troubleshooting
---

# Troubleshooting

## `brain: command not found`

The `brain` executable is not on your PATH.

**If you installed via pip:**

```bash
# Check where pip installed it
pip show shared-brain

# Common fix: add pip's bin directory to PATH
export PATH="$HOME/.local/bin:$PATH"

# Make it permanent
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

**If you installed from source with a symlink:**

```bash
# Check the symlink exists
ls -la ~/bin/brain

# If missing, recreate it
ln -s /path/to/shared-brain/brain ~/bin/brain

# Make sure ~/bin is on PATH
export PATH="$HOME/bin:$PATH"
echo 'export PATH="$HOME/bin:$PATH"' >> ~/.bashrc
```

**If you installed from source with pip -e:**

```bash
# Reinstall in editable mode
cd /path/to/shared-brain
pip install -e .

# Verify
which brain
```

## Lessons not loading

### Symptoms

- `brain list` shows fewer lessons than expected
- `brain guard` does not match patterns that should match
- "No lessons found" when you know lessons exist

### Check BRAIN_HOME

Custom lessons live in `$BRAIN_HOME/lessons/` (defaults to `~/.brain/lessons/`). If `BRAIN_HOME` is set incorrectly, brain looks in the wrong place:

```bash
# See where brain is looking
echo ${BRAIN_HOME:-~/.brain}

# List lessons in that directory
ls -la ${BRAIN_HOME:-~/.brain}/lessons/
```

### Check file permissions

Lesson files must be readable:

```bash
ls -la ~/.brain/lessons/
# Files should show -rw-r--r-- or similar

# Fix permissions if needed
chmod 644 ~/.brain/lessons/*.yaml
```

### Check YAML syntax

A malformed YAML file is skipped with a warning on stderr. Run brain with stderr visible:

```bash
brain list 2>&1
```

Look for lines like `Warning: Failed to load /path/to/file.yaml: ...`.

Common YAML issues:
- **Missing quotes around strings with colons**: Use `"https://example.com"` not `https://example.com`
- **Indentation with tabs**: YAML requires spaces, not tabs
- **Missing `id` field**: Every lesson needs an `id`

### Check for duplicate IDs

Lessons with the same `id` are deduplicated. The first one loaded wins (custom lessons are loaded before built-in ones). If a custom lesson has the same `id` as a built-in, the custom one takes precedence:

```bash
# Search for duplicate IDs
grep -r "^id:" ~/.brain/lessons/ /path/to/shared-brain/lessons/ | sort -t: -k3 | uniq -d -f2
```

## Guard not firing (pattern mismatch)

### Symptoms

- You run a command that should trigger a lesson, but guard says nothing
- The lesson exists and is loaded (visible in `brain list`)

### Debug pattern matching

First, confirm the lesson loads:

```bash
brain check "your-lesson-id"
```

Then test the pattern manually. Trigger patterns use Python `re.search()` with `re.IGNORECASE`. Test in Python:

```python
import re
pattern = r"curl.*-X PUT"
command = "curl -X PUT https://api.example.com/articles/123"
print(bool(re.search(pattern, command, re.IGNORECASE)))
```

### Common pattern issues

**Special characters not escaped**: Regex special characters like `.`, `(`, `)`, `+` need escaping:

```yaml
# Wrong: matches any character before "put"
trigger_patterns:
  - "requests.put"

# Right: matches literal dot
trigger_patterns:
  - "requests\\.put"
```

**Pattern too specific**: The pattern must match the actual command string brain guard receives:

```yaml
# This only matches if the command literally contains "PUT /api/"
trigger_patterns:
  - "PUT /api/"

# This matches curl commands with -X PUT anywhere in the URL
trigger_patterns:
  - "curl.*-X PUT"
```

**Word boundaries**: Use `\b` to avoid matching substrings:

```yaml
# Matches "rm" inside "format" — probably not wanted
trigger_patterns:
  - "rm"

# Matches only the rm command
trigger_patterns:
  - "\\brm\\b"
```

### Test with brain guard directly

```bash
# Verbose test — see if your command triggers anything
brain guard "your exact command here"
```

## Hook not installed properly

### Symptoms

- `brain hook status` shows "Not installed"
- Claude Code runs Bash commands without guard checks
- `brain hook install` says it installed but nothing happens

### Check settings.json

The hook lives in `~/.claude/settings.json`:

```bash
cat ~/.claude/settings.json
```

Look for the PreToolUse section:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "/path/to/shared-brain/brain guard --from-env"
          }
        ]
      }
    ]
  }
}
```

### Common issues

**Wrong path in hook command**: The hook stores the absolute path to the `brain` executable. If you moved the shared-brain directory after installing, the path is stale:

```bash
# Reinstall the hook
brain hook uninstall
brain hook install
```

**settings.json has invalid JSON**: If you hand-edited the file and introduced a syntax error:

```bash
# Validate the JSON
python3 -m json.tool ~/.claude/settings.json
```

**Multiple hooks conflicting**: If another PreToolUse hook is interfering, check the order in settings.json. Hooks run in the order they appear.

### Reinstall from scratch

```bash
brain hook uninstall
brain hook install
brain hook status
# Should show: 🟢 Installed
```

## Audit file corrupt

### Symptoms

- `brain audit` shows an error or no data
- `brain stats` crashes or shows incorrect numbers

### Diagnose

The audit file is `~/.brain/audit.jsonl` (one JSON object per line). Check for corruption:

```bash
# Count valid vs invalid lines
python3 -c "
import json
valid = invalid = 0
with open('$HOME/.brain/audit.jsonl') as f:
    for i, line in enumerate(f, 1):
        line = line.strip()
        if not line:
            continue
        try:
            json.loads(line)
            valid += 1
        except json.JSONDecodeError:
            invalid += 1
            print(f'Line {i}: INVALID')
print(f'Valid: {valid}, Invalid: {invalid}')
"
```

### Fix: Remove invalid lines

```bash
python3 -c "
import json
lines = open('$HOME/.brain/audit.jsonl').readlines()
valid = []
for line in lines:
    line = line.strip()
    if not line:
        continue
    try:
        json.loads(line)
        valid.append(line + '\n')
    except json.JSONDecodeError:
        pass
open('$HOME/.brain/audit.jsonl', 'w').writelines(valid)
print(f'Kept {len(valid)} valid entries')
"
```

### Fix: Start fresh

If the file is beyond repair:

```bash
# Back up first
cp ~/.brain/audit.jsonl ~/.brain/audit.jsonl.bak

# Reset
rm ~/.brain/audit.jsonl
```

A new file will be created on the next `brain guard` call.

## Performance issues with many lessons

### Symptoms

- `brain guard` takes noticeably longer than usual
- Guard latency exceeds 200ms

### Benchmark your setup

```bash
brain benchmark
```

This runs 1000 guard checks against all loaded lessons and reports latency percentiles.

### Reduce lesson count

Guard latency scales linearly with the number of lessons. If you have more than 100 lessons:

1. **Archive old lessons**: Move rarely-triggered lessons to a backup directory:

```bash
mkdir -p ~/.brain/lessons-archive
mv ~/.brain/lessons/old-lesson.yaml ~/.brain/lessons-archive/
```

Brain only scans `~/.brain/lessons/`, so archived files are not loaded.

2. **Consolidate overlapping lessons**: If multiple lessons have similar trigger patterns, merge them:

```yaml
# Instead of 3 separate API lessons, combine them
id: api-safety
trigger_patterns:
  - "curl.*-X PUT"
  - "curl.*-X DELETE"
  - "curl.*-X PATCH"
lesson: |
  Destructive API operations require extra care.
  ...
```

### Check for ReDoS patterns

Regex patterns with nested quantifiers can cause catastrophic backtracking. Shared Brain includes a heuristic check for this, but if you suspect a slow pattern:

```bash
# Find lessons with complex patterns
grep -r "trigger_patterns" ~/.brain/lessons/ -A 5
```

Avoid patterns like `(a+)+`, `(a*)*`, or `(a|b)*c` with overlapping alternation.

## YAML parsing without PyYAML

### Symptoms

- Lesson files with advanced YAML features do not load correctly
- Warning messages about failed parsing

### What the built-in parser supports

Shared Brain's fallback parser handles the lesson format:

- Key-value pairs (`key: value`)
- Lists (`- "item"`)
- Multiline strings (`key: |`)
- Inline lists (`tags: [a, b, c]`)
- Nested key-value one level deep (`source:` with `incident:` and `url:`)
- Quoted and unquoted strings
- Comments (`# comment`)

### What it does NOT support

- Anchors and aliases (`&anchor`, `*alias`)
- Multi-document files (`---` separators)
- Flow mappings (`{key: value}`)
- Complex nested structures beyond one level
- Custom YAML tags (`!!python/object`)

### Fix: Install PyYAML

If you need full YAML support:

```bash
pip install pyyaml
```

Shared Brain automatically detects and uses PyYAML when available. No configuration needed.

### Fix: Simplify lesson files

If you cannot install PyYAML, keep lessons in the supported subset:

```yaml
id: my-lesson
severity: warning
trigger_patterns:
  - "pattern"
lesson: |
  Description here.
checklist:
  - "Step 1"
tags: [tag1, tag2]
```

This format works identically with and without PyYAML.

## Getting more help

- [GitHub Issues](https://github.com/yurukusa/shared-brain/issues) -- Report bugs or ask questions
- [Tutorial](./tutorial) -- Step-by-step guide for new users
- [FAQ](./faq) -- Answers to common questions
- Run `brain help` for a quick command reference
