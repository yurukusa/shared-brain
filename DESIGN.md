# Shared Brain - AI Agent Lesson Learning System

## One-Line Pitch
**"AI agents that learn from each other's mistakes — and prove it."**

## The Problem (Real Story)

Day 1: Claude Code used `PUT /api/articles` without first doing `GET`. One article's body was overwritten with just a footer. We wrote the lesson: "Always GET before PUT."

Day 2: **Same agent, same mistake.** All 5 Zenn articles deleted. A reader discovered it.

The lesson existed. The agent didn't read it. **Writing lessons is useless if nobody checks them.**

## The Solution: Shared Brain

A CLI tool + lightweight server that:
1. **Stores** structured lessons from any agent
2. **Guards** — automatically checks relevant lessons before risky operations
3. **Tracks** — records whether agents read AND followed lessons
4. **Audits** — shows compliance: who checked, who didn't, what broke

### The Key Innovation: `brain guard`

```bash
# Before any API call, brain guard fires automatically
$ brain guard "PUT /api/articles/my-article"

⚠️  CRITICAL LESSON (violated 2x, last: 2026-02-09):
    "PUT replaces entire resource. Always GET first."
    Source: zenn-deletion-incident

    Checklist:
    [ ] Did you GET the current state?
    [ ] Does your PUT body contain ALL fields?

Proceed? [y/N]
```

This isn't "write a lesson and hope." This is **"the system stops you before you repeat the mistake."**

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│  Agent A     │────▶│  Shared Brain │◀────│  Agent B    │
│  (Claude     │     │  Server       │     │  (Claude    │
│   Code #1)   │     │              │     │   Code #2)  │
└─────────────┘     │  - Lessons DB │     └─────────────┘
                    │  - Guard Rules│
                    │  - Audit Log  │
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐
                    │  brain CLI    │
                    │  (local tool) │
                    └──────────────┘
```

### Components

#### 1. Lesson Store (`~/.brain/lessons/`)
YAML files, human-readable, git-trackable.

```yaml
# ~/.brain/lessons/api-put-safety.yaml
id: api-put-safety
severity: critical
created: 2026-02-08
violated_count: 2
last_violated: 2026-02-09

trigger_patterns:
  - "PUT /api/"
  - "requests.put"
  - "curl.*-X PUT"
  - "fetch.*method.*PUT"

lesson: |
  PUT replaces the entire resource. Fields not included in the
  request body will be overwritten with empty/default values.

  ALWAYS:
  1. GET the current state first
  2. Modify only the fields you need
  3. Send ALL fields in the PUT body

checklist:
  - "GET the current resource state"
  - "PUT body contains ALL required fields"
  - "Test on 1 item before batch operation"

source:
  incident: "Zenn 5-article deletion"
  url: "https://zenn.dev/yurukusa/articles/fc378dfbb37a5b"

tags: [api, destructive, data-loss]
```

#### 2. Guard Engine (`brain guard`)
Pattern-matching pre-hook that intercepts risky operations.

```
Input: command string or code snippet
  ↓
Match against trigger_patterns in all lessons
  ↓
If match found:
  - Display lesson + checklist
  - Log the check (timestamp, agent, lesson_id, action)
  - Require explicit acknowledgment
  ↓
If no match: pass through silently
```

#### 3. Audit Log (`~/.brain/audit.jsonl`)
```json
{"timestamp": "2026-02-09T10:30:00Z", "agent": "cc-main", "action": "PUT /api/articles/abc", "lesson_matched": "api-put-safety", "checked": true, "followed": true}
{"timestamp": "2026-02-09T10:31:00Z", "agent": "cc-sub-3", "action": "PUT /api/articles/def", "lesson_matched": "api-put-safety", "checked": false, "followed": false, "incident": "article body overwritten"}
```

#### 4. Brain CLI Commands

| Command | Description |
|---------|-------------|
| `brain write` | Add a new lesson (interactive or from file) |
| `brain guard <command>` | Check command against lessons |
| `brain check <topic>` | Search lessons by topic/keyword |
| `brain audit` | Show compliance report |
| `brain list` | List all lessons |
| `brain stats` | Violation counts, compliance rate |
| `brain hook install` | Install as pre-commit/pre-exec hook |

## Integration Points

### As Claude Code Hook (PostToolUse / PreToolUse)
```json
{
  "hooks": {
    "PreToolUse": [{
      "matcher": "Bash|Edit|Write",
      "command": "brain guard \"$TOOL_INPUT\""
    }]
  }
}
```

### As Shell Alias
```bash
alias curl='brain guard curl'
alias wget='brain guard wget'
```

### As Git Pre-Commit Hook
```bash
#!/bin/bash
brain guard "git commit" || exit 1
```

## Hackathon Demo Flow (5 minutes)

### Act 1: The Problem (1 min)
"Watch what happens when an AI agent updates an article..."
- Show: agent does PUT without GET
- Result: article body deleted
- "We wrote the lesson. But the next day..."
- Show: same agent, same mistake, 5 articles gone

### Act 2: Shared Brain (2 min)
"Now with Shared Brain installed..."
- Show: agent tries PUT
- brain guard fires: "⚠️ CRITICAL: Always GET before PUT"
- Agent acknowledges, does GET first
- Article updated safely
- Audit log shows: checked ✅, followed ✅

### Act 3: Multi-Agent (1 min)
"But what about OTHER agents?"
- Show: a different agent (subagent) tries PUT
- brain guard fires for them too — lesson shared across agents
- "The lesson was learned once. Every agent benefits."

### Act 4: Audit Dashboard (1 min)
- Show: `brain stats`
- Compliance rate: 100% since installation
- Violations: 0 (down from 2)
- "This is the proof. Not that we wrote the lesson — that we followed it."

## Tech Stack (Keep Simple for Hackathon)

- **Language**: Bash + Python (no heavy dependencies)
- **Storage**: YAML files (lessons) + JSONL (audit log)
- **No server needed for MVP** — purely file-based, like git
- **Optional**: Simple web dashboard (single HTML file) for audit visualization

## File Structure
```
shared-brain/
├── brain              # Main CLI (Bash entry point)
├── brain_engine.py    # Core logic (Python)
├── lessons/           # Built-in lesson templates
│   ├── api-put-safety.yaml
│   ├── git-force-push.yaml
│   └── ...
├── tests/
│   └── test_guard.py
├── DESIGN.md          # This file
├── README.md          # User-facing docs
└── demo/
    ├── demo_script.sh # Hackathon demo script
    └── demo.html      # Audit dashboard
```

## MVP Scope (Today)

1. [x] Design doc (this file)
2. [ ] `brain` CLI with `write`, `guard`, `check`, `list`, `audit` commands
3. [ ] 3 built-in lessons (PUT safety, force push, destructive delete)
4. [ ] Audit logging (JSONL)
5. [ ] Demo script for hackathon
6. [ ] README with installation instructions

## Post-Hackathon

- MCP server integration (brain as an MCP tool)
- Web dashboard with real-time compliance metrics
- Lesson sharing across teams (brain sync)
- Integration with CI/CD pipelines
- Lesson templates marketplace
