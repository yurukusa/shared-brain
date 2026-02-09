# Contributing to Shared Brain

Thanks for your interest in contributing!

## Getting Started

```bash
git clone https://github.com/yurukusa/shared-brain.git
cd shared-brain
```

No external dependencies required — Shared Brain uses only the Python standard library.

## Running Tests

```bash
pip install pytest
python -m pytest tests/ -v
```

## Project Structure

```
shared-brain/
  brain              # Shell entrypoint
  brain_engine.py    # Core CLI (all logic lives here)
  lessons/           # Built-in lessons (shipped with the tool)
  tests/             # pytest test suite
  DESIGN.md          # Architecture and design decisions
```

## Adding a Built-in Lesson

1. Create a YAML file in `lessons/`:

```yaml
id: your-lesson-id
severity: critical|warning|info
trigger_patterns:
  - "regex or substring to match"
lesson: |
  What went wrong and why.
checklist:
  - "Step 1 to verify"
  - "Step 2 to verify"
tags: [relevant, tags]
```

2. Run tests to make sure nothing breaks:
```bash
python -m pytest tests/ -v
```

3. Submit a PR.

## Writing Custom Lessons

Users store their own lessons in `~/.brain/lessons/`. These are separate from built-in lessons and won't conflict.

## Code Style

- Python 3.8+ compatible
- No external dependencies (stdlib only)
- Keep `brain_engine.py` as a single file for easy distribution
- YAML parsing uses a built-in lightweight parser (no PyYAML needed)

## Reporting Issues

Open an issue on GitHub with:
- What you expected
- What happened
- Steps to reproduce
- Output of `brain stats`

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
