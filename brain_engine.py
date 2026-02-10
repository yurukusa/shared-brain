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
import subprocess
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
                if not lesson or not isinstance(lesson, dict):
                    continue
                lesson["_file"] = str(f)
                lid = lesson.get("id", f.stem)
                if lid not in seen_ids:
                    seen_ids.add(lid)
                    lessons.append(lesson)
            except Exception as e:
                print(f"Warning: Failed to load {f}: {e}", file=sys.stderr)

    return lessons


# --- Security helpers ---

def _check_regex_safety(pattern: str) -> bool:
    """Heuristic check for patterns likely to cause catastrophic backtracking (ReDoS).

    Detects nested quantifiers and overlapping alternation — the most common ReDoS causes.
    Returns True if the pattern looks safe, False if suspicious.
    """
    # Nested quantifiers: (x+)+, (x*)+, (x+)*, (x*)*
    if re.search(r'\([^)]*[+*][^)]*\)\s*[+*?]', pattern):
        return False
    # Overlapping alternation under quantifier: (a|a)+
    if re.search(r'\([^)]*\|[^)]*\)\s*[+*]', pattern):
        return False
    return True


def _safe_regex_search(pattern: str, text: str, timeout: float = 0.5):
    """Regex search with ReDoS protection.

    - Safe-looking patterns: uses re.search() directly (fast)
    - Suspicious patterns: uses a subprocess with hard timeout (safe)
    - Invalid patterns: raises re.error for the caller to handle

    Returns a match object or truthy value if found, None if no match or timeout.
    """
    # Validate syntax first
    try:
        re.compile(pattern, re.IGNORECASE)
    except re.error:
        raise

    if _check_regex_safety(pattern):
        # Fast path: pattern looks safe, use directly
        return re.search(pattern, text, re.IGNORECASE)

    # Suspicious pattern: use subprocess for hard timeout (GIL-proof)
    script = (
        f"import re,sys\n"
        f"m=re.search({pattern!r},{text!r},re.IGNORECASE)\n"
        f"sys.exit(0 if m else 1)"
    )
    try:
        result = subprocess.run(
            [sys.executable, "-c", script],
            timeout=timeout,
            capture_output=True,
        )
        return True if result.returncode == 0 else None
    except subprocess.TimeoutExpired:
        print(f"Warning: Regex pattern timed out (possible ReDoS): {pattern[:50]}", file=sys.stderr)
        return None


def _sanitize_lesson_id(lid: str) -> str:
    """Sanitize lesson ID to prevent path traversal.

    Only allows word characters (including Unicode), hyphens, and dots (not ..).
    Strips directory separators and parent references.
    """
    # Remove path separators and parent directory references
    sanitized = re.sub(r'[/\\]', '', lid)
    sanitized = re.sub(r'\.\.+', '', sanitized)
    # Remove remaining non-word characters except hyphens
    sanitized = re.sub(r'[^\w-]', '', sanitized, flags=re.UNICODE)
    if not sanitized:
        raise ValueError(f"Invalid lesson ID after sanitization: '{lid}'")
    return sanitized


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
                if _safe_regex_search(pattern, command):
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
    """Load all audit entries. Skips corrupt lines gracefully."""
    if not AUDIT_FILE.exists():
        return []
    try:
        text = AUDIT_FILE.read_text()
    except (OSError, IOError) as e:
        print(f"Warning: Could not read audit file: {e}", file=sys.stderr)
        return []
    if not text.strip():
        return []
    entries = []
    for i, line in enumerate(text.strip().split("\n"), 1):
        if not line.strip():
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            print(f"Warning: Skipping corrupt audit entry on line {i}", file=sys.stderr)
    return entries


# --- Commands ---

def cmd_write(args):
    """Add a new lesson."""
    if args and args[0] == "-f" and len(args) > 1:
        # From file
        src = Path(args[1])
        if not src.exists():
            print(f"Error: File not found: {src}", file=sys.stderr)
            print(f"  The YAML file '{src}' does not exist.", file=sys.stderr)
            print(f"  Create it first, or use 'brain write' to add a lesson interactively.", file=sys.stderr)
            return 1
        lesson = load_yaml(src)
        raw_lid = lesson.get("id", src.stem)
        try:
            lid = _sanitize_lesson_id(raw_lid)
        except ValueError:
            print(f"Error: Invalid lesson ID '{raw_lid}'.", file=sys.stderr)
            print(f"  Lesson IDs must contain only word characters and hyphens.", file=sys.stderr)
            print(f"  Path separators (/, \\) and '..' are not allowed.", file=sys.stderr)
            return 1
        dest = LESSONS_DIR / f"{lid}.yaml"
        # Defense-in-depth: verify destination stays inside LESSONS_DIR
        if not str(dest.resolve()).startswith(str(LESSONS_DIR.resolve())):
            print(f"Error: Path traversal detected in lesson ID '{raw_lid}'.", file=sys.stderr)
            return 1
        import shutil
        shutil.copy2(src, dest)
        print(f"✅ Lesson '{lid}' written to {dest}")
        return 0

    # Interactive mode
    print("📝 New Lesson")
    print("-" * 40)

    raw_lid = input("ID (short, kebab-case): ").strip()
    if not raw_lid:
        print("Aborted.")
        return 1
    try:
        lid = _sanitize_lesson_id(raw_lid)
    except ValueError:
        print(f"Error: Invalid lesson ID '{raw_lid}'. Use only word characters and hyphens.")
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
    from_env = "--from-env" in args
    args = [a for a in args if a not in ("--auto-confirm", "--from-env")]

    if from_env:
        # Read tool input from environment variable (safe from shell injection)
        tool_input_raw = os.environ.get("TOOL_INPUT", "")
        if not tool_input_raw:
            return 0  # No input to check
        try:
            tool_input = json.loads(tool_input_raw)
            command = tool_input.get("command", "")
        except (json.JSONDecodeError, TypeError):
            # Not JSON, use as-is
            command = tool_input_raw
        if not command:
            return 0
    elif args:
        command = " ".join(args)
    else:
        print("Error: No command specified.", file=sys.stderr)
        print("  brain guard checks a command against known lessons before execution.", file=sys.stderr)
        print("  Usage: brain guard \"curl -X PUT https://api.example.com/articles/123\"", file=sys.stderr)
        return 1

    agent = os.environ.get("BRAIN_AGENT", "cli-user")

    safe = guard(command, agent, auto_confirm=auto_confirm)
    return 0 if safe else 1


def cmd_check(args):
    """Search lessons by keyword."""
    if not args:
        print("Error: No keyword specified.", file=sys.stderr)
        print("  brain check searches all lessons by keyword.", file=sys.stderr)
        print("  Usage: brain check \"PUT\" or brain check \"api safety\"", file=sys.stderr)
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
        print("Error: Missing or invalid hook subcommand.", file=sys.stderr)
        print("  brain hook manages the Claude Code PreToolUse integration.", file=sys.stderr)
        print("  Usage: brain hook install | brain hook uninstall | brain hook status", file=sys.stderr)
        return 1

    settings_path = Path.home() / ".claude" / "settings.json"
    brain_cmd = str(Path(__file__).parent / "brain")

    # The hook entry we want to add/remove
    # Uses --from-env to read $TOOL_INPUT via os.environ (avoids shell injection)
    hook_entry = {
        "matcher": "Bash",
        "hooks": [
            {
                "type": "command",
                "command": f"{brain_cmd} guard --from-env"
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


def cmd_export(args):
    """Export lessons to Markdown or JSON format."""
    fmt = "md"
    output_file = None

    # Parse args
    i = 0
    while i < len(args):
        if args[i] == "--format" and i + 1 < len(args):
            fmt = args[i + 1].lower()
            i += 2
        elif args[i] == "--output" and i + 1 < len(args):
            output_file = args[i + 1]
            i += 2
        else:
            i += 1

    if fmt not in ("md", "json", "markdown"):
        print(f"Error: Unknown format '{fmt}'.", file=sys.stderr)
        print(f"  Supported formats: 'md' (Markdown) and 'json'.", file=sys.stderr)
        print(f"  Usage: brain export --format md --output lessons.md", file=sys.stderr)
        return 1

    lessons = load_all_lessons()

    if fmt in ("md", "markdown"):
        lines = ["# Shared Brain — Exported Lessons", ""]
        lines.append(f"*{len(lessons)} lessons exported on {datetime.date.today().isoformat()}*")
        lines.append("")

        for lesson in lessons:
            severity = lesson.get("severity", "info").upper()
            lid = lesson.get("id", "unknown")
            icon = "🔴" if severity == "CRITICAL" else "🟡" if severity == "WARNING" else "🔵"

            lines.append(f"## {icon} {lid}")
            lines.append(f"**Severity:** {severity}")

            text = lesson.get("lesson", "")
            if text:
                lines.append("")
                lines.append(text.strip())

            checklist = lesson.get("checklist", [])
            if checklist:
                lines.append("")
                for item in checklist:
                    lines.append(f"- [ ] {item}")

            patterns = lesson.get("trigger_patterns", [])
            if patterns:
                lines.append("")
                lines.append(f"**Triggers:** `{'`, `'.join(patterns)}`")

            tags = lesson.get("tags", [])
            if tags:
                tag_list = tags if isinstance(tags, list) else [tags]
                lines.append(f"**Tags:** {', '.join(tag_list)}")

            lines.append("")
            lines.append("---")
            lines.append("")

        content = "\n".join(lines)
    else:
        # JSON export — strip internal fields
        clean = []
        for lesson in lessons:
            entry = {k: v for k, v in lesson.items() if not k.startswith("_")}
            clean.append(entry)
        content = json.dumps(clean, indent=2, ensure_ascii=False)

    if output_file:
        Path(output_file).write_text(content)
        print(f"✅ Exported {len(lessons)} lessons to {output_file}")
    else:
        print(content)

    return 0


def cmd_benchmark(args):
    """Run performance benchmark."""
    benchmark_script = Path(__file__).parent / "tests" / "benchmark.py"
    if not benchmark_script.exists():
        print(f"Error: Benchmark script not found.", file=sys.stderr)
        print(f"  Expected at: {benchmark_script}", file=sys.stderr)
        print(f"  This file ships with the source repo. Try: git clone && cd shared-brain", file=sys.stderr)
        return 1
    os.execvp(sys.executable, [sys.executable, str(benchmark_script)])


def cmd_demo(args):
    """Offline demo mode — pre-populated sandbox with sample data."""
    import tempfile
    import shutil

    CYAN = "\033[1;36m"
    GREEN = "\033[1;32m"
    YELLOW = "\033[1;33m"
    BOLD = "\033[1m"
    RESET = "\033[0m"

    print(f"""
{CYAN}╔══════════════════════════════════════════════╗
║         🧠 Shared Brain Demo Mode            ║
║                                              ║
║  A sandbox with pre-loaded lessons and       ║
║  audit data. Try every command risk-free.    ║
╚══════════════════════════════════════════════╝{RESET}
""")

    # Create temp sandbox
    demo_dir = Path(tempfile.mkdtemp(prefix="brain-demo-"))
    demo_lessons = demo_dir / "lessons"
    demo_lessons.mkdir()
    demo_audit = demo_dir / "audit"
    demo_audit.mkdir()

    # Save originals
    original_brain_dir = BRAIN_DIR
    original_lessons = LESSONS_DIR
    original_audit = AUDIT_FILE

    # Point module globals to sandbox (including BUILTIN_LESSONS to isolate demo)
    _mod = sys.modules[__name__]
    original_builtin = BUILTIN_LESSONS
    _mod.BRAIN_DIR = demo_dir
    _mod.LESSONS_DIR = demo_lessons
    _mod.AUDIT_FILE = demo_dir / "audit.jsonl"
    _mod.BUILTIN_LESSONS = demo_dir / "no-builtins"  # Non-existent dir to suppress built-ins

    try:
        # Create demo lessons
        demo_lesson_data = [
            {
                "id": "api-put-safety",
                "severity": "critical",
                "created": "2026-02-08",
                "violated_count": 2,
                "last_violated": "2026-02-09",
                "trigger_patterns": [r"PUT\s+/api/", r"curl.*-X\s+PUT", r"requests\.put"],
                "lesson": "PUT replaces the ENTIRE resource.\nAlways GET before PUT to preserve existing fields.",
                "checklist": ["GET the current resource state", "PUT body contains ALL required fields"],
                "source": {"incident": "Zenn article overwrite — 5 articles deleted by PUT without GET"},
                "tags": ["api", "data-safety"],
            },
            {
                "id": "git-force-push",
                "severity": "critical",
                "created": "2026-02-03",
                "violated_count": 1,
                "trigger_patterns": [r"git push.*--force", r"git reset.*--hard", r"rm\s+-rf"],
                "lesson": "Force push, hard reset, and rm -rf are destructive and hard to reverse.\nAlways create a backup branch first.",
                "checklist": ["Created backup branch", "Verified current branch", "User explicitly requested"],
                "source": {"incident": "Draemorth project destruction"},
                "tags": ["git", "destructive"],
            },
            {
                "id": "verify-before-claim",
                "severity": "warning",
                "created": "2026-02-09",
                "violated_count": 3,
                "trigger_patterns": [r"echo.*done", r"echo.*complete", r"echo.*success"],
                "lesson": "Never claim a task is complete without verifying the result.\nAlways check the actual output, not just the exit code.",
                "checklist": ["Ran verification command", "Checked actual output", "Took screenshot if external"],
                "tags": ["verification", "quality"],
            },
            {
                "id": "test-before-deploy",
                "severity": "warning",
                "created": "2026-02-10",
                "violated_count": 0,
                "trigger_patterns": [r"deploy.*prod", r"kubectl apply", r"terraform apply"],
                "lesson": "Always run tests before deploying to production.\nA passing CI pipeline is not enough — run tests locally too.",
                "checklist": ["Tests pass locally", "CI pipeline green", "Rollback plan exists"],
                "tags": ["deploy", "testing"],
            },
        ]

        for lesson in demo_lesson_data:
            dump_yaml(lesson, demo_lessons / f"{lesson['id']}.yaml")

        # Create demo audit entries
        audit_entries = [
            {"timestamp": "2026-02-09T08:15:00Z", "agent": "cc-main", "action": "curl -X PUT https://api.zenn.dev/articles/abc", "lessons_matched": ["api-put-safety"], "checked": True, "followed": False, "note": "user_aborted"},
            {"timestamp": "2026-02-09T08:20:00Z", "agent": "cc-main", "action": "curl -X GET https://api.zenn.dev/articles/abc", "lessons_matched": [], "checked": True, "followed": True, "note": "no_match"},
            {"timestamp": "2026-02-09T08:21:00Z", "agent": "cc-main", "action": "curl -X PUT https://api.zenn.dev/articles/abc", "lessons_matched": ["api-put-safety"], "checked": True, "followed": True, "note": "user_confirmed"},
            {"timestamp": "2026-02-09T10:30:00Z", "agent": "cc-dev", "action": "git push --force origin main", "lessons_matched": ["git-force-push"], "checked": True, "followed": False, "note": "user_aborted"},
            {"timestamp": "2026-02-09T14:00:00Z", "agent": "cc-main", "action": "echo 'deployment complete'", "lessons_matched": ["verify-before-claim"], "checked": True, "followed": True, "note": "user_confirmed"},
            {"timestamp": "2026-02-10T09:00:00Z", "agent": "cc-main", "action": "ls -la", "lessons_matched": [], "checked": True, "followed": True, "note": "no_match"},
            {"timestamp": "2026-02-10T11:30:00Z", "agent": "cc-dev", "action": "curl -X PUT https://api.example.com/data", "lessons_matched": ["api-put-safety"], "checked": True, "followed": True, "note": "user_confirmed"},
        ]

        with open(_mod.AUDIT_FILE, "w") as f:
            for entry in audit_entries:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")

        print(f"{GREEN}Sandbox created with:{RESET}")
        print(f"  • 4 lessons (2 critical, 2 warning)")
        print(f"  • 7 audit entries across 2 agents")
        print(f"  • Sandbox dir: {demo_dir}")
        print()
        print(f"{BOLD}Try these commands:{RESET}")
        print()
        print(f"  {CYAN}brain list{RESET}             — See all demo lessons")
        print(f"  {CYAN}brain guard \"curl -X PUT ...\"{RESET}  — Trigger a guard")
        print(f"  {CYAN}brain check \"PUT\"{RESET}      — Search lessons")
        print(f"  {CYAN}brain audit{RESET}             — View compliance report")
        print(f"  {CYAN}brain stats{RESET}             — Quick stats")
        print(f"  {CYAN}brain export --format md{RESET} — Export lessons")
        print()

        # Run the requested subcommand, or start interactive mode
        if args:
            subcmd = args[0]
            subargs = args[1:]
            if subcmd in COMMANDS:
                COMMANDS[subcmd](subargs)
            else:
                print(f"Unknown demo command: {subcmd}")
        else:
            # Show list + audit as default demo experience
            print(f"{YELLOW}{'─'*50}{RESET}")
            print(f"{YELLOW}  Demo: brain list{RESET}")
            print(f"{YELLOW}{'─'*50}{RESET}")
            cmd_list([])

            print(f"{YELLOW}{'─'*50}{RESET}")
            print(f"{YELLOW}  Demo: brain audit{RESET}")
            print(f"{YELLOW}{'─'*50}{RESET}")
            cmd_audit([])

            print(f"{YELLOW}{'─'*50}{RESET}")
            print(f"{YELLOW}  Demo: brain stats{RESET}")
            print(f"{YELLOW}{'─'*50}{RESET}")
            cmd_stats([])

            print(f"\n{GREEN}Demo complete!{RESET} Run {CYAN}brain demo <command>{RESET} to try specific commands.")

    finally:
        # Restore original paths
        _mod.BRAIN_DIR = original_brain_dir
        _mod.LESSONS_DIR = original_lessons
        _mod.AUDIT_FILE = original_audit
        _mod.BUILTIN_LESSONS = original_builtin
        shutil.rmtree(demo_dir, ignore_errors=True)

    return 0


def cmd_tutorial(args):
    """Interactive tutorial — walk through lesson creation, guard, and audit."""
    import time

    CYAN = "\033[1;36m"
    GREEN = "\033[1;32m"
    YELLOW = "\033[1;33m"
    RED = "\033[1;31m"
    BOLD = "\033[1m"
    RESET = "\033[0m"

    def step(num, title):
        print(f"\n{CYAN}{'─'*50}{RESET}")
        print(f"{CYAN}  Step {num}: {title}{RESET}")
        print(f"{CYAN}{'─'*50}{RESET}\n")

    def pause(msg="Press Enter to continue..."):
        if sys.stdin.isatty():
            input(f"\n{BOLD}{msg}{RESET}")
        else:
            print()

    print(f"""
{CYAN}╔══════════════════════════════════════════════╗
║         🧠 Shared Brain Tutorial             ║
║                                              ║
║  Learn how to create lessons, guard commands,║
║  and audit compliance — in 3 steps.          ║
╚══════════════════════════════════════════════╝{RESET}
""")

    # --- Step 1: Create a tutorial lesson ---
    step(1, "Create a lesson")

    tutorial_lesson_id = "tutorial-example"
    tutorial_file = LESSONS_DIR / f"{tutorial_lesson_id}.yaml"

    print(f"""Lessons teach agents what {RED}not{RESET} to do.
Each lesson has:
  • {BOLD}trigger_patterns{RESET} — regex patterns that match risky commands
  • {BOLD}severity{RESET} — critical, warning, or info
  • {BOLD}checklist{RESET} — steps to verify before proceeding

Let's create a sample lesson that catches {RED}rm -rf{RESET} commands.""")

    pause()

    lesson_data = {
        "id": tutorial_lesson_id,
        "severity": "critical",
        "created": datetime.date.today().isoformat(),
        "violated_count": 0,
        "trigger_patterns": [
            r"rm\s+-rf",
            r"rm\s+-r\s+/",
        ],
        "lesson": "rm -rf can permanently delete files with no recovery.\n"
                  "Always double-check the path and consider using trash instead.",
        "checklist": [
            "Verify the target path is correct",
            "Ensure important files are backed up",
            "Consider using 'trash' or moving to a temp directory",
        ],
        "source": {
            "incident": "Tutorial example — common agent mistake",
        },
        "tags": ["filesystem", "destructive", "tutorial"],
    }

    dump_yaml(lesson_data, tutorial_file)
    print(f"""{GREEN}✅ Created lesson:{RESET} {tutorial_lesson_id}
   File: {tutorial_file}

   Here's what it looks like as YAML:""")
    print()
    print(f"   {YELLOW}id:{RESET} {tutorial_lesson_id}")
    print(f"   {YELLOW}severity:{RESET} critical")
    print(f"   {YELLOW}trigger_patterns:{RESET}")
    print(f'     - "rm\\s+-rf"')
    print(f'     - "rm\\s+-r\\s+/"')
    print(f"   {YELLOW}lesson:{RESET} |")
    print(f"     rm -rf can permanently delete files...")
    print(f"   {YELLOW}checklist:{RESET}")
    print(f"     - Verify the target path is correct")
    print(f"     - Ensure important files are backed up")

    # --- Step 2: Test the guard ---
    step(2, "Test the guard")

    print(f"""Now let's see what happens when an agent tries to run
a command that matches our lesson.

Running: {BOLD}brain guard "rm -rf /tmp/old-data"{RESET}
""")

    pause("Press Enter to trigger the guard...")
    print()

    # Simulate guard output (non-blocking version)
    guard("rm -rf /tmp/old-data", agent="tutorial-user", auto_confirm=True)

    print(f"""
{GREEN}The guard matched the command against our lesson and showed
the warning with a checklist.{RESET}

In real usage:
  • As a {BOLD}CLI command{RESET}: the user sees this and types y/N
  • As a {BOLD}Claude Code hook{RESET}: it fires automatically before
    every Bash command, blocking dangerous operations""")

    # --- Step 3: Check the audit ---
    step(3, "Check the audit trail")

    print(f"""Every guard check is logged to {BOLD}~/.brain/audit.jsonl{RESET}.
Let's see what was recorded:
""")

    pause("Press Enter to view the audit...")
    print()

    entries = load_audit()
    if entries:
        last = entries[-1]
        ts = last.get("timestamp", "?")[:19]
        agent = last.get("agent", "?")
        action = last.get("action", "?")
        note = last.get("note", "")
        lessons_matched = last.get("lessons_matched", [])

        print(f"  {GREEN}Latest audit entry:{RESET}")
        print(f"    Timestamp: {ts}")
        print(f"    Agent:     {agent}")
        print(f"    Action:    {action}")
        print(f"    Lessons:   {', '.join(lessons_matched) if lessons_matched else 'none'}")
        print(f"    Result:    {note}")
    else:
        print("  (No audit entries found)")

    # --- Wrap up ---
    print(f"""
{CYAN}{'─'*50}{RESET}
{CYAN}  Tutorial Complete!{RESET}
{CYAN}{'─'*50}{RESET}

{GREEN}You've learned the core workflow:{RESET}

  1. {BOLD}brain write{RESET}     — Create lessons from incidents
  2. {BOLD}brain guard{RESET}     — Check commands before execution
  3. {BOLD}brain audit{RESET}     — Prove compliance with data

{BOLD}Next steps:{RESET}
  • Run {CYAN}brain list{RESET} to see all built-in lessons
  • Run {CYAN}brain hook install{RESET} to auto-guard Claude Code
  • Run {CYAN}brain write{RESET} to create your own lesson
""")

    # Clean up tutorial lesson
    if tutorial_file.exists():
        tutorial_file.unlink()
        print(f"  (Tutorial lesson cleaned up)")

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
  brain export [--format md|json] [--output file]
                              Export lessons for other projects
  brain hook install          Auto-install guard as Claude Code hook
  brain hook uninstall        Remove brain guard hook
  brain hook status           Check if hook is installed
  brain tutorial              Interactive walkthrough for new users

Environment:
  BRAIN_HOME    Override brain directory (default: ~/.brain)
  BRAIN_AGENT   Set agent name for audit logging

Examples:
  brain guard "curl -X PUT https://api.example.com/articles/123"
  brain check "api safety"
  brain write -f my-lesson.yaml
  brain export --format json --output lessons.json
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
    "export": cmd_export,
    "hook": cmd_hook,
    "tutorial": cmd_tutorial,
    "demo": cmd_demo,
    "benchmark": cmd_benchmark,
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
        print(f"Error: Unknown command '{cmd}'.", file=sys.stderr)
        print(f"  Available commands: write, guard, check, list, audit, stats, export, hook, tutorial, benchmark", file=sys.stderr)
        print(f"  Run 'brain help' for detailed usage.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main() or 0)
