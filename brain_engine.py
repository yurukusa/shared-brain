#!/usr/bin/env python3
"""
Shared Brain Engine - Core logic for the brain CLI.
AI agents that learn from each other's mistakes — and prove it.
"""

import sys
import os
import json
import re
import datetime
import glob as globmod
from pathlib import Path

try:
    import yaml
except ImportError:
    # Fallback: minimal YAML parsing for environments without PyYAML
    yaml = None

BRAIN_DIR = Path(os.environ.get("BRAIN_HOME", Path.home() / ".brain"))
LESSONS_DIR = BRAIN_DIR / "lessons"
AUDIT_FILE = BRAIN_DIR / "audit.jsonl"
BUILTIN_LESSONS = Path(__file__).parent / "lessons"


def ensure_dirs():
    LESSONS_DIR.mkdir(parents=True, exist_ok=True)
    (BRAIN_DIR / "audit").mkdir(parents=True, exist_ok=True)


# --- YAML helpers (works with or without PyYAML) ---

def load_yaml(path: Path) -> dict:
    """Load a YAML file into a dict."""
    if yaml:
        with open(path) as f:
            return yaml.safe_load(f)
    else:
        return _parse_yaml_simple(path.read_text())


def dump_yaml(data: dict, path: Path):
    """Write a dict to a YAML file."""
    if yaml:
        with open(path, "w") as f:
            yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
    else:
        _write_yaml_simple(data, path)


def _parse_yaml_simple(text: str) -> dict:
    """Minimal YAML parser for simple key-value + list structures."""
    result = {}
    current_key = None
    current_list = None
    multiline_key = None
    multiline_lines = []

    for line in text.split("\n"):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            if multiline_key:
                multiline_lines.append("")
            continue

        # Multiline block scalar end detection
        if multiline_key and not line.startswith("  "):
            result[multiline_key] = "\n".join(multiline_lines).strip()
            multiline_key = None
            multiline_lines = []

        if multiline_key:
            multiline_lines.append(line.strip())
            continue

        # Top-level key: value
        m = re.match(r'^(\w[\w_-]*)\s*:\s*(.*)', line)
        if m:
            key, val = m.group(1), m.group(2).strip()
            current_key = key
            current_list = None

            if val == "|":
                multiline_key = key
                multiline_lines = []
            elif val.startswith("[") and val.endswith("]"):
                # Inline list
                items = [x.strip().strip("'\"") for x in val[1:-1].split(",") if x.strip()]
                result[key] = items
            elif val == "":
                result[key] = None
            elif val.lower() in ("true", "false"):
                result[key] = val.lower() == "true"
            elif val.isdigit():
                result[key] = int(val)
            else:
                result[key] = val.strip("'\"")
            continue

        # List item under current key
        m = re.match(r'^  - (.*)', line)
        if m and current_key:
            val = m.group(1).strip().strip('"\'')
            if current_key not in result or not isinstance(result.get(current_key), list):
                result[current_key] = []
            result[current_key].append(val)
            continue

        # Nested key (simple one-level)
        m = re.match(r'^  (\w[\w_-]*)\s*:\s*(.*)', line)
        if m and current_key:
            if not isinstance(result.get(current_key), dict):
                result[current_key] = {}
            nk, nv = m.group(1), m.group(2).strip().strip("'\"")
            result[current_key][nk] = nv

    if multiline_key:
        result[multiline_key] = "\n".join(multiline_lines).strip()

    return result


def _write_yaml_simple(data: dict, path: Path):
    """Minimal YAML writer."""
    lines = []
    for k, v in data.items():
        if isinstance(v, list):
            lines.append(f"{k}:")
            for item in v:
                lines.append(f'  - "{item}"')
        elif isinstance(v, dict):
            lines.append(f"{k}:")
            for nk, nv in v.items():
                lines.append(f"  {nk}: {nv}")
        elif isinstance(v, bool):
            lines.append(f"{k}: {'true' if v else 'false'}")
        elif isinstance(v, int):
            lines.append(f"{k}: {v}")
        elif isinstance(v, str) and "\n" in v:
            lines.append(f"{k}: |")
            for line in v.split("\n"):
                lines.append(f"  {line}")
        else:
            lines.append(f"{k}: {v}")
        lines.append("")
    path.write_text("\n".join(lines))


# --- Lesson loading ---

def get_all_lesson_dirs():
    """Return all directories that contain lessons."""
    dirs = [LESSONS_DIR]
    if BUILTIN_LESSONS.exists():
        dirs.append(BUILTIN_LESSONS)
    return dirs


def load_all_lessons() -> list:
    """Load all lessons from all sources."""
    lessons = []
    seen_ids = set()

    for d in get_all_lesson_dirs():
        for f in sorted(d.glob("*.yaml")) + sorted(d.glob("*.yml")):
            try:
                lesson = load_yaml(f)
                lesson["_file"] = str(f)
                lid = lesson.get("id", f.stem)
                if lid not in seen_ids:
                    seen_ids.add(lid)
                    lessons.append(lesson)
            except Exception as e:
                print(f"Warning: Failed to load {f}: {e}", file=sys.stderr)

    return lessons


# --- Guard engine ---

def guard(command: str, agent: str = "unknown", auto_confirm: bool = False) -> bool:
    """Check a command against all lessons. Returns True if safe to proceed."""
    lessons = load_all_lessons()
    matches = []

    for lesson in lessons:
        patterns = lesson.get("trigger_patterns", [])
        if not patterns:
            continue
        for pattern in patterns:
            try:
                if re.search(pattern, command, re.IGNORECASE):
                    matches.append(lesson)
                    break
            except re.error:
                # Fall back to simple substring match
                if pattern.lower() in command.lower():
                    matches.append(lesson)
                    break

    if not matches:
        # No matching lessons — safe to proceed
        log_audit(agent, command, None, checked=True, followed=True, note="no_match")
        return True

    # Display warnings
    for lesson in matches:
        severity = lesson.get("severity", "info").upper()
        lid = lesson.get("id", "unknown")
        violated = lesson.get("violated_count", 0)
        last_violated = lesson.get("last_violated", "never")

        # Color codes
        if severity == "CRITICAL":
            color = "\033[1;31m"  # Bold red
        elif severity == "WARNING":
            color = "\033[1;33m"  # Bold yellow
        else:
            color = "\033[1;36m"  # Bold cyan
        reset = "\033[0m"

        print(f"\n{color}{'='*60}{reset}")
        print(f"{color}⚠️  {severity} LESSON: {lid}{reset}")
        if violated > 0:
            print(f"{color}   (violated {violated}x, last: {last_violated}){reset}")
        print(f"{'='*60}")

        # Lesson text
        lesson_text = lesson.get("lesson", "No description available.")
        for line in lesson_text.strip().split("\n"):
            print(f"   {line}")

        # Checklist
        checklist = lesson.get("checklist", [])
        if checklist:
            print(f"\n   {color}Checklist:{reset}")
            for item in checklist:
                print(f"   [ ] {item}")

        # Source
        source = lesson.get("source", {})
        if isinstance(source, dict) and source.get("incident"):
            print(f"\n   Source: {source['incident']}")

        print()

    # Log the check
    lesson_ids = [m.get("id", "unknown") for m in matches]

    # Auto-confirm mode (for demos and hooks): show prompt, log as confirmed
    if auto_confirm:
        print("Proceed? [y/N] y  (auto-confirmed)")
        log_audit(agent, command, lesson_ids, checked=True, followed=True, note="user_confirmed")
        return True

    # Log guard trigger for non-auto-confirm paths
    log_audit(agent, command, lesson_ids, checked=True, followed=None, note="guard_triggered")

    # In interactive mode, ask for confirmation
    if sys.stdin.isatty():
        try:
            response = input("Proceed? [y/N] ").strip().lower()
            proceeded = response in ("y", "yes")
            log_audit(agent, command, lesson_ids, checked=True, followed=proceeded,
                      note="user_confirmed" if proceeded else "user_aborted")
            return proceeded
        except (EOFError, KeyboardInterrupt):
            print("\nAborted.")
            log_audit(agent, command, lesson_ids, checked=True, followed=False, note="interrupted")
            return False
    else:
        # Non-interactive: warn but don't block
        print("⚠️  Running in non-interactive mode. Proceeding with caution.")
        return True


# --- Audit logging ---

def log_audit(agent: str, action: str, lesson_ids, checked: bool, followed, note: str = ""):
    """Append an audit entry."""
    ensure_dirs()
    entry = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "agent": agent,
        "action": action[:200],  # Truncate long commands
        "lessons_matched": lesson_ids if lesson_ids else [],
        "checked": checked,
        "followed": followed,
        "note": note,
    }
    with open(AUDIT_FILE, "a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def load_audit() -> list:
    """Load all audit entries."""
    if not AUDIT_FILE.exists():
        return []
    entries = []
    for line in AUDIT_FILE.read_text().strip().split("\n"):
        if line.strip():
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return entries


# --- Commands ---

def cmd_write(args):
    """Add a new lesson."""
    if args and args[0] == "-f" and len(args) > 1:
        # From file
        src = Path(args[1])
        if not src.exists():
            print(f"Error: File not found: {src}", file=sys.stderr)
            return 1
        lesson = load_yaml(src)
        lid = lesson.get("id", src.stem)
        dest = LESSONS_DIR / f"{lid}.yaml"
        import shutil
        shutil.copy2(src, dest)
        print(f"✅ Lesson '{lid}' written to {dest}")
        return 0

    # Interactive mode
    print("📝 New Lesson")
    print("-" * 40)

    lid = input("ID (short, kebab-case): ").strip()
    if not lid:
        print("Aborted.")
        return 1

    severity = input("Severity (critical/warning/info) [warning]: ").strip() or "warning"
    lesson_text = input("Lesson (what should agents know?): ").strip()

    patterns = []
    print("Trigger patterns (regex, empty line to finish):")
    while True:
        p = input("  pattern> ").strip()
        if not p:
            break
        patterns.append(p)

    checklist = []
    print("Checklist items (empty line to finish):")
    while True:
        c = input("  check> ").strip()
        if not c:
            break
        checklist.append(c)

    data = {
        "id": lid,
        "severity": severity,
        "created": datetime.date.today().isoformat(),
        "violated_count": 0,
        "trigger_patterns": patterns,
        "lesson": lesson_text,
        "checklist": checklist,
        "tags": [],
    }

    dest = LESSONS_DIR / f"{lid}.yaml"
    dump_yaml(data, dest)
    print(f"\n✅ Lesson '{lid}' saved to {dest}")
    return 0


def cmd_guard(args):
    """Check a command against lessons."""
    auto_confirm = "--auto-confirm" in args
    args = [a for a in args if a != "--auto-confirm"]

    if not args:
        print("Usage: brain guard <command or code snippet>", file=sys.stderr)
        return 1

    command = " ".join(args)
    agent = os.environ.get("BRAIN_AGENT", "cli-user")

    safe = guard(command, agent, auto_confirm=auto_confirm)
    return 0 if safe else 1


def cmd_check(args):
    """Search lessons by keyword."""
    if not args:
        print("Usage: brain check <keyword>", file=sys.stderr)
        return 1

    keyword = " ".join(args).lower()
    lessons = load_all_lessons()
    found = []

    for lesson in lessons:
        searchable = json.dumps(lesson, ensure_ascii=False, default=str).lower()
        if keyword in searchable:
            found.append(lesson)

    if not found:
        print(f"No lessons found for '{keyword}'")
        return 0

    print(f"Found {len(found)} lesson(s) matching '{keyword}':\n")
    for lesson in found:
        severity = lesson.get("severity", "info").upper()
        lid = lesson.get("id", "unknown")
        text = lesson.get("lesson", "")
        # Truncate to first line
        first_line = text.split("\n")[0][:80] if text else "(no description)"
        violated = lesson.get("violated_count", 0)

        icon = "🔴" if severity == "CRITICAL" else "🟡" if severity == "WARNING" else "🔵"
        print(f"  {icon} [{lid}] {first_line}")
        if violated > 0:
            print(f"     ⚠️  Violated {violated} time(s)")
    return 0


def cmd_list(args):
    """List all lessons."""
    lessons = load_all_lessons()

    if not lessons:
        print("No lessons found. Use 'brain write' to add one.")
        return 0

    print(f"📚 {len(lessons)} lesson(s):\n")
    for lesson in lessons:
        severity = lesson.get("severity", "info").upper()
        lid = lesson.get("id", "unknown")
        violated = lesson.get("violated_count", 0)
        patterns = lesson.get("trigger_patterns", [])
        source_file = lesson.get("_file", "")
        is_builtin = "lessons/" in source_file and str(BUILTIN_LESSONS) in source_file

        icon = "🔴" if severity == "CRITICAL" else "🟡" if severity == "WARNING" else "🔵"
        loc = " (built-in)" if is_builtin else ""

        text = lesson.get("lesson", "")
        first_line = text.split("\n")[0][:60] if text else "(no description)"

        print(f"  {icon} {lid}{loc}")
        print(f"     {first_line}")
        if patterns:
            print(f"     Triggers: {', '.join(patterns[:3])}")
        if violated:
            print(f"     ⚠️  Violated {violated}x")
        print()
    return 0


def cmd_audit(args):
    """Show compliance report."""
    entries = load_audit()
    as_json = "--json" in args

    if as_json:
        print(json.dumps(entries, indent=2, ensure_ascii=False))
        return 0

    if not entries:
        print("No audit entries yet.")
        return 0

    # Group by lesson
    lesson_stats = {}
    total_checks = 0
    total_followed = 0
    total_blocked = 0

    for entry in entries:
        for lid in entry.get("lessons_matched", []):
            if lid not in lesson_stats:
                lesson_stats[lid] = {"checks": 0, "followed": 0, "blocked": 0}
            lesson_stats[lid]["checks"] += 1
            if entry.get("followed") is True:
                lesson_stats[lid]["followed"] += 1
            elif entry.get("followed") is False:
                lesson_stats[lid]["blocked"] += 1
            total_checks += 1
            if entry.get("followed") is True:
                total_followed += 1
            elif entry.get("followed") is False:
                total_blocked += 1

    print("📊 Audit Report")
    print("=" * 50)
    print(f"Total checks: {total_checks}")
    print(f"Followed:     {total_followed}")
    print(f"Blocked:      {total_blocked}")
    if total_checks > 0:
        rate = (total_followed / total_checks) * 100
        print(f"Compliance:   {rate:.0f}%")
    print()

    if lesson_stats:
        print("Per-lesson breakdown:")
        for lid, stats in sorted(lesson_stats.items()):
            print(f"  [{lid}] checks={stats['checks']}, followed={stats['followed']}, blocked={stats['blocked']}")

    # Recent entries
    print(f"\nLast 10 entries:")
    for entry in entries[-10:]:
        ts = entry.get("timestamp", "?")[:19]
        agent = entry.get("agent", "?")
        action = entry.get("action", "?")[:50]
        note = entry.get("note", "")
        followed = entry.get("followed")
        icon = "✅" if followed is True else "❌" if followed is False else "⚪"
        print(f"  {icon} {ts} [{agent}] {action} ({note})")

    return 0


def cmd_stats(args):
    """Quick stats summary."""
    lessons = load_all_lessons()
    entries = load_audit()

    total_lessons = len(lessons)
    critical = sum(1 for l in lessons if l.get("severity") == "critical")
    total_violations = sum(l.get("violated_count", 0) for l in lessons)

    guard_triggers = sum(1 for e in entries if e.get("note") in ("guard_triggered", "user_confirmed", "user_aborted"))
    user_confirmed = sum(1 for e in entries if e.get("note") == "user_confirmed")
    user_aborted = sum(1 for e in entries if e.get("note") == "user_aborted")

    print("🧠 Shared Brain Stats")
    print("=" * 40)
    print(f"Lessons:       {total_lessons} ({critical} critical)")
    print(f"Violations:    {total_violations} (historical)")
    print(f"Guard fires:   {guard_triggers}")
    print(f"Proceeded:     {user_confirmed}")
    print(f"Aborted:       {user_aborted}")

    if guard_triggers > 0:
        prevention_rate = (user_aborted / guard_triggers) * 100
        print(f"Prevention:    {prevention_rate:.0f}% (mistakes caught)")

    return 0


def cmd_hook(args):
    """Install or uninstall brain guard as a Claude Code hook."""
    if not args or args[0] not in ("install", "uninstall", "status"):
        print("Usage: brain hook install|uninstall|status", file=sys.stderr)
        return 1

    settings_path = Path.home() / ".claude" / "settings.json"
    brain_cmd = str(Path(__file__).parent / "brain")

    # The hook entry we want to add/remove
    hook_entry = {
        "matcher": "Bash",
        "hooks": [
            {
                "type": "command",
                "command": f"{brain_cmd} guard \"$TOOL_INPUT\""
            }
        ]
    }

    if args[0] == "status":
        if not settings_path.exists():
            print("⚪ Not installed (settings.json not found)")
            return 0
        settings = json.loads(settings_path.read_text())
        hooks = settings.get("hooks", {}).get("PreToolUse", [])
        installed = any("brain guard" in json.dumps(h) for h in hooks)
        print(f"{'🟢 Installed' if installed else '⚪ Not installed'}")
        return 0

    if args[0] == "uninstall":
        if not settings_path.exists():
            print("Nothing to uninstall (settings.json not found)")
            return 0
        settings = json.loads(settings_path.read_text())
        hooks = settings.get("hooks", {}).get("PreToolUse", [])
        new_hooks = [h for h in hooks if "brain guard" not in json.dumps(h)]
        if len(new_hooks) == len(hooks):
            print("⚪ Brain guard hook not found in settings")
            return 0
        settings["hooks"]["PreToolUse"] = new_hooks
        settings_path.write_text(json.dumps(settings, indent=2, ensure_ascii=False) + "\n")
        print("🗑️  Brain guard hook removed from Claude Code")
        return 0

    # --- install ---
    if not settings_path.exists():
        # Create minimal settings with our hook
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        settings = {"hooks": {"PreToolUse": [hook_entry]}}
        settings_path.write_text(json.dumps(settings, indent=2, ensure_ascii=False) + "\n")
        print(f"🧠 Brain guard installed! (created {settings_path})")
        return 0

    settings = json.loads(settings_path.read_text())

    # Check if already installed
    existing_hooks = settings.get("hooks", {}).get("PreToolUse", [])
    if any("brain guard" in json.dumps(h) for h in existing_hooks):
        print("🟢 Brain guard hook already installed")
        return 0

    # Merge into existing settings
    if "hooks" not in settings:
        settings["hooks"] = {}
    if "PreToolUse" not in settings["hooks"]:
        settings["hooks"]["PreToolUse"] = []

    settings["hooks"]["PreToolUse"].append(hook_entry)
    settings_path.write_text(json.dumps(settings, indent=2, ensure_ascii=False) + "\n")
    print(f"🧠 Brain guard installed into Claude Code!")
    print(f"   Every Bash command will now be checked against lessons.")
    print(f"   Run 'brain hook status' to verify.")
    return 0


def cmd_help(args=None):
    """Show help."""
    print("""🧠 Shared Brain - AI agents that learn from each other's mistakes

Usage:
  brain write                 Add a new lesson interactively
  brain write -f <file.yaml>  Add a lesson from a YAML file
  brain guard <command>       Check command against known lessons
  brain check <keyword>       Search lessons by keyword
  brain list                  List all lessons
  brain audit [--json]        Show compliance report
  brain stats                 Quick stats summary
  brain hook install          Auto-install guard as Claude Code hook
  brain hook uninstall        Remove brain guard hook
  brain hook status           Check if hook is installed

Environment:
  BRAIN_HOME    Override brain directory (default: ~/.brain)
  BRAIN_AGENT   Set agent name for audit logging

Examples:
  brain guard "curl -X PUT https://api.example.com/articles/123"
  brain check "api safety"
  brain write -f my-lesson.yaml
""")
    return 0


# --- Main ---

COMMANDS = {
    "write": cmd_write,
    "guard": cmd_guard,
    "check": cmd_check,
    "list": cmd_list,
    "audit": cmd_audit,
    "stats": cmd_stats,
    "hook": cmd_hook,
    "help": cmd_help,
    "--help": cmd_help,
    "-h": cmd_help,
}


def main():
    ensure_dirs()

    if len(sys.argv) < 2:
        cmd_help()
        return 0

    cmd = sys.argv[1]
    args = sys.argv[2:]

    if cmd in COMMANDS:
        return COMMANDS[cmd](args)
    else:
        print(f"Unknown command: {cmd}", file=sys.stderr)
        print("Run 'brain help' for usage.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main() or 0)
