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

# --- i18n ---
# Lazy-imported to avoid import errors when messages/ dir is missing
_msg_func = None

def msg(key: str, **kwargs) -> str:
    """Get translated message. Lazy-loads i18n on first call."""
    global _msg_func
    if _msg_func is None:
        try:
            from brain_i18n import msg as _real_msg
            _msg_func = _real_msg
        except ImportError:
            # Fallback: return key as-is if i18n module not available
            def _fallback(key, **kw):
                return key
            _msg_func = _fallback
    return _msg_func(key, **kwargs)


BRAIN_DIR = Path(os.environ.get("BRAIN_HOME", Path.home() / ".brain"))
LESSONS_DIR = BRAIN_DIR / "lessons"
AUDIT_FILE = BRAIN_DIR / "audit.jsonl"
BUILTIN_LESSONS = Path(__file__).parent / "lessons"
PLUGINS_DIR = BRAIN_DIR / "plugins"


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


# --- Plugin System ---

class PluginRegistry:
    """Registry for plugin extensions."""

    def __init__(self):
        self.guards = []       # list of GuardPlugin dicts
        self.exporters = {}    # format_name -> export_fn
        self.sources = []      # list of SourcePlugin dicts
        self._loaded = False

    def register_guard(self, name: str, match_fn, check_fn=None, priority: int = 50):
        """Register a custom guard rule."""
        self.guards.append({
            "name": name,
            "match_fn": match_fn,
            "check_fn": check_fn,
            "priority": priority,
        })
        # Keep sorted by priority
        self.guards.sort(key=lambda g: g["priority"])

    def register_exporter(self, format_name: str, export_fn):
        """Register a custom export format."""
        self.exporters[format_name] = export_fn

    def register_source(self, name: str, load_fn):
        """Register a custom lesson source."""
        self.sources.append({"name": name, "load_fn": load_fn})


REGISTRY = PluginRegistry()


def load_plugins():
    """Load plugins from ~/.brain/plugins/ directory."""
    if REGISTRY._loaded:
        return
    REGISTRY._loaded = True

    if not PLUGINS_DIR.exists():
        return

    for plugin_file in sorted(PLUGINS_DIR.glob("*.py")):
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location(
                f"brain_plugin_{plugin_file.stem}", plugin_file
            )
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            if hasattr(mod, "register"):
                mod.register(REGISTRY)
        except Exception as e:
            print(f"Warning: Plugin '{plugin_file.name}' failed to load: {e}", file=sys.stderr)


# --- Lesson loading ---

def get_all_lesson_dirs():
    """Return all directories that contain lessons."""
    dirs = [LESSONS_DIR]
    if BUILTIN_LESSONS.exists():
        dirs.append(BUILTIN_LESSONS)
    return dirs


def load_all_lessons() -> list:
    """Load all lessons from all sources (local YAML + plugin sources)."""
    load_plugins()
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

    # Plugin sources
    for source in REGISTRY.sources:
        try:
            plugin_lessons = source["load_fn"]()
            for lesson in plugin_lessons:
                lid = lesson.get("id", "")
                if lid and lid not in seen_ids:
                    seen_ids.add(lid)
                    lessons.append(lesson)
        except Exception as e:
            print(f"Warning: Plugin source '{source['name']}' failed: {e}", file=sys.stderr)

    return lessons


# --- Security helpers ---

def _check_regex_safety(pattern: str) -> bool:
    """Heuristic check for patterns likely to cause catastrophic backtracking (ReDoS)."""
    if re.search(r'\([^)]*[+*][^)]*\)\s*[+*?]', pattern):
        return False
    if re.search(r'\([^)]*\|[^)]*\)\s*[+*]', pattern):
        return False
    return True


def _safe_regex_search(pattern: str, text: str, timeout: float = 0.5):
    """Regex search with ReDoS protection."""
    try:
        re.compile(pattern, re.IGNORECASE)
    except re.error:
        raise

    if _check_regex_safety(pattern):
        return re.search(pattern, text, re.IGNORECASE)

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
        print(msg("warn_regex_timeout", pattern=pattern[:50]), file=sys.stderr)
        return None


def _sanitize_lesson_id(lid: str) -> str:
    """Sanitize lesson ID to prevent path traversal."""
    sanitized = re.sub(r'[/\\]', '', lid)
    sanitized = re.sub(r'\.\.+', '', sanitized)
    sanitized = re.sub(r'[^\w-]', '', sanitized, flags=re.UNICODE)
    if not sanitized:
        raise ValueError(f"Invalid lesson ID after sanitization: '{lid}'")
    return sanitized


# --- Guard engine ---

def guard(command: str, agent: str = "unknown", auto_confirm: bool = False) -> bool:
    """Check a command against all lessons. Returns True if safe to proceed."""
    lessons = load_all_lessons()
    matches = []

    # Built-in trigger pattern matching
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
                if pattern.lower() in command.lower():
                    matches.append(lesson)
                    break

    # Plugin guard rules
    for pg in REGISTRY.guards:
        try:
            if pg["match_fn"](command):
                result = pg["check_fn"](command, lessons) if pg["check_fn"] else None
                if result and isinstance(result, dict):
                    # Plugin guard results are displayed like lessons
                    matches.append(result)
        except Exception as e:
            print(f"Warning: Guard plugin '{pg['name']}' failed: {e}", file=sys.stderr)

    if not matches:
        log_audit(agent, command, None, checked=True, followed=True, note="no_match")
        return True

    # Display warnings
    for lesson in matches:
        severity = lesson.get("severity", "info").upper()
        lid = lesson.get("id", "unknown")
        violated = lesson.get("violated_count", 0)
        last_violated = lesson.get("last_violated", "never")

        if severity == "CRITICAL":
            color = "\033[1;31m"
        elif severity == "WARNING":
            color = "\033[1;33m"
        else:
            color = "\033[1;36m"
        reset = "\033[0m"

        print(f"\n{color}{'='*60}{reset}")
        print(f"{color}\u26a0\ufe0f  {severity} LESSON: {lid}{reset}")
        if violated > 0:
            print(f"{color}   (violated {violated}x, last: {last_violated}){reset}")
        print(f"{'='*60}")

        lesson_text = lesson.get("lesson", msg("guard_no_description"))
        for line in lesson_text.strip().split("\n"):
            print(f"   {line}")

        checklist = lesson.get("checklist", [])
        if checklist:
            print(f"\n   {color}{msg('guard_checklist_header')}{reset}")
            for item in checklist:
                print(f"   [ ] {item}")

        source = lesson.get("source", {})
        if isinstance(source, dict) and source.get("incident"):
            print(f"\n   {msg('guard_source_label', incident=source['incident'])}")

        # Plugin guard message field
        if "message" in lesson and "lesson" not in lesson:
            print(f"   {lesson['message']}")

        print()

    lesson_ids = [m.get("id", "unknown") for m in matches]

    if auto_confirm:
        print(msg("proceed_auto_confirmed"))
        log_audit(agent, command, lesson_ids, checked=True, followed=True, note="user_confirmed")
        return True

    log_audit(agent, command, lesson_ids, checked=True, followed=None, note="guard_triggered")

    if sys.stdin.isatty():
        try:
            response = input(msg("proceed_prompt")).strip().lower()
            proceeded = response in ("y", "yes")
            log_audit(agent, command, lesson_ids, checked=True, followed=proceeded,
                      note="user_confirmed" if proceeded else "user_aborted")
            return proceeded
        except (EOFError, KeyboardInterrupt):
            print(f"\n{msg('aborted')}")
            log_audit(agent, command, lesson_ids, checked=True, followed=False, note="interrupted")
            return False
    else:
        print(f"\u26a0\ufe0f  {msg('non_interactive_warning')}")
        return True


# --- Audit logging ---

def log_audit(agent: str, action: str, lesson_ids, checked: bool, followed, note: str = ""):
    """Append an audit entry."""
    ensure_dirs()
    entry = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "agent": agent,
        "action": action[:200],
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
        print(msg("warn_audit_read_failed", error=str(e)), file=sys.stderr)
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
            print(msg("warn_audit_corrupt_line", line_num=i), file=sys.stderr)
    return entries


# --- Commands ---

def cmd_write(args):
    """Add a new lesson."""
    if args and args[0] == "-f" and len(args) > 1:
        src = Path(args[1])
        if not src.exists():
            print(msg("write_error_file_not_found", src=src), file=sys.stderr)
            print(msg("write_error_file_not_found_detail", src=src), file=sys.stderr)
            print(msg("write_error_file_not_found_hint"), file=sys.stderr)
            return 1
        lesson = load_yaml(src)
        raw_lid = lesson.get("id", src.stem)
        try:
            lid = _sanitize_lesson_id(raw_lid)
        except ValueError:
            print(msg("write_error_invalid_id", raw_lid=raw_lid), file=sys.stderr)
            print(msg("write_error_invalid_id_detail"), file=sys.stderr)
            print(msg("write_error_invalid_id_path_sep"), file=sys.stderr)
            return 1
        dest = LESSONS_DIR / f"{lid}.yaml"
        if not str(dest.resolve()).startswith(str(LESSONS_DIR.resolve())):
            print(msg("write_error_path_traversal", raw_lid=raw_lid), file=sys.stderr)
            return 1
        import shutil
        shutil.copy2(src, dest)
        print(f"\u2705 {msg('write_success_from_file', lid=lid, dest=dest)}")
        return 0

    # Interactive mode
    print(f"\U0001f4dd {msg('write_header')}")
    print("-" * 40)

    raw_lid = input(msg("write_prompt_id")).strip()
    if not raw_lid:
        print(msg("aborted"))
        return 1
    try:
        lid = _sanitize_lesson_id(raw_lid)
    except ValueError:
        print(msg("write_error_invalid_id_short", raw_lid=raw_lid))
        return 1

    severity = input(msg("write_prompt_severity")).strip() or "warning"
    lesson_text = input(msg("write_prompt_lesson")).strip()

    patterns = []
    print(msg("write_prompt_trigger_intro"))
    while True:
        p = input(msg("write_prompt_trigger")).strip()
        if not p:
            break
        patterns.append(p)

    checklist = []
    print(msg("write_prompt_checklist_intro"))
    while True:
        c = input(msg("write_prompt_checklist")).strip()
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
    print(f"\u2705 {msg('write_success_interactive', lid=lid, dest=dest)}")
    return 0


def cmd_guard(args):
    """Check a command against lessons."""
    auto_confirm = "--auto-confirm" in args
    from_env = "--from-env" in args
    args = [a for a in args if a not in ("--auto-confirm", "--from-env")]

    if from_env:
        tool_input_raw = os.environ.get("TOOL_INPUT", "")
        if not tool_input_raw:
            return 0
        try:
            tool_input = json.loads(tool_input_raw)
            command = tool_input.get("command", "")
        except (json.JSONDecodeError, TypeError):
            command = tool_input_raw
        if not command:
            return 0
    elif args:
        command = " ".join(args)
    else:
        print(msg("guard_error_no_command"), file=sys.stderr)
        print(msg("guard_error_no_command_desc"), file=sys.stderr)
        print(msg("guard_error_no_command_usage"), file=sys.stderr)
        return 1

    agent = os.environ.get("BRAIN_AGENT", "cli-user")

    safe = guard(command, agent, auto_confirm=auto_confirm)
    return 0 if safe else 1


def cmd_check(args):
    """Search lessons by keyword."""
    if not args:
        print(msg("check_error_no_keyword"), file=sys.stderr)
        print(msg("check_error_no_keyword_desc"), file=sys.stderr)
        print(msg("check_error_no_keyword_usage"), file=sys.stderr)
        return 1

    keyword = " ".join(args).lower()
    lessons = load_all_lessons()
    found = []

    for lesson in lessons:
        searchable = json.dumps(lesson, ensure_ascii=False, default=str).lower()
        if keyword in searchable:
            found.append(lesson)

    if not found:
        print(msg("check_no_results", keyword=keyword))
        return 0

    print(msg("check_found", keyword=keyword, count=len(found)))
    for lesson in found:
        severity = lesson.get("severity", "info").upper()
        lid = lesson.get("id", "unknown")
        text = lesson.get("lesson", "")
        first_line = text.split("\n")[0][:80] if text else msg("check_no_description")
        violated = lesson.get("violated_count", 0)

        icon = "\U0001f534" if severity == "CRITICAL" else "\U0001f7e1" if severity == "WARNING" else "\U0001f535"
        print(f"  {icon} [{lid}] {first_line}")
        if violated > 0:
            print(msg("check_violated_count", count=violated))
    return 0


def cmd_list(args):
    """List all lessons."""
    lessons = load_all_lessons()

    if not lessons:
        print(msg("list_empty"))
        return 0

    print(f"\U0001f4da {msg('list_header', count=len(lessons))}")
    for lesson in lessons:
        severity = lesson.get("severity", "info").upper()
        lid = lesson.get("id", "unknown")
        violated = lesson.get("violated_count", 0)
        patterns = lesson.get("trigger_patterns", [])
        source_file = lesson.get("_file", "")
        is_builtin = "lessons/" in source_file and str(BUILTIN_LESSONS) in source_file

        icon = "\U0001f534" if severity == "CRITICAL" else "\U0001f7e1" if severity == "WARNING" else "\U0001f535"
        loc = msg("list_builtin_label") if is_builtin else ""

        text = lesson.get("lesson", "")
        first_line = text.split("\n")[0][:60] if text else msg("list_no_description")

        print(f"  {icon} {lid}{loc}")
        print(f"     {first_line}")
        if patterns:
            print(msg("list_triggers_label", triggers=", ".join(patterns[:3])))
        if violated:
            print(f"     \u26a0\ufe0f  {msg('list_violated_label', count=violated)}")
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
        print(msg("audit_empty"))
        return 0

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

    print(f"\U0001f4ca {msg('audit_header')}")
    print("=" * 50)
    print(msg("audit_total_checks", count=total_checks))
    print(msg("audit_followed", count=total_followed))
    print(msg("audit_blocked", count=total_blocked))
    if total_checks > 0:
        rate = (total_followed / total_checks) * 100
        print(msg("audit_compliance", rate=rate))
    print()

    if lesson_stats:
        print(msg("audit_per_lesson"))
        for lid, stats in sorted(lesson_stats.items()):
            print(f"  [{lid}] checks={stats['checks']}, followed={stats['followed']}, blocked={stats['blocked']}")

    print(msg("audit_last_entries", count=10))
    for entry in entries[-10:]:
        ts = entry.get("timestamp", "?")[:19]
        agent = entry.get("agent", "?")
        action = entry.get("action", "?")[:50]
        note = entry.get("note", "")
        followed = entry.get("followed")
        icon = "\u2705" if followed is True else "\u274c" if followed is False else "\u26aa"
        print(f"  {icon} {ts} [{agent}] {action} ({note})")

    return 0


def cmd_stats(args):
    """Quick stats summary. Use --verbose for detailed breakdown."""
    verbose = "--verbose" in args or "-v" in args
    lessons = load_all_lessons()
    entries = load_audit()

    total_lessons = len(lessons)
    critical = sum(1 for l in lessons if l.get("severity") == "critical")
    warning = sum(1 for l in lessons if l.get("severity") == "warning")
    info = total_lessons - critical - warning
    total_violations = sum(l.get("violated_count", 0) for l in lessons)

    guard_triggers = sum(1 for e in entries if e.get("note") in ("guard_triggered", "user_confirmed", "user_aborted"))
    user_confirmed = sum(1 for e in entries if e.get("note") == "user_confirmed")
    user_aborted = sum(1 for e in entries if e.get("note") == "user_aborted")

    print(f"\U0001f9e0 {msg('stats_header')}")
    print("=" * 40)
    print(msg("stats_lessons", total=total_lessons, critical=critical))
    print(msg("stats_violations", count=total_violations))
    print(msg("stats_guard_fires", count=guard_triggers))
    print(msg("stats_proceeded", count=user_confirmed))
    print(msg("stats_aborted", count=user_aborted))

    if guard_triggers > 0:
        prevention_rate = (user_aborted / guard_triggers) * 100
        print(msg("stats_prevention", rate=prevention_rate))

    if not verbose:
        return 0

    # --- Verbose output ---
    BOLD = "\033[1m"
    CYAN = "\033[1;36m"
    RESET = "\033[0m"

    print(f"\n{BOLD}{msg('stats_severity_header')}{RESET}")
    print(f"  \U0001f534 {msg('stats_severity_critical', count=critical)}")
    print(f"  \U0001f7e1 {msg('stats_severity_warning', count=warning)}")
    print(f"  \U0001f535 {msg('stats_severity_info', count=info)}")

    tag_counts = {}
    for lesson in lessons:
        tags = lesson.get("tags", [])
        if isinstance(tags, str):
            tags = [tags]
        for tag in tags:
            tag_counts[tag] = tag_counts.get(tag, 0) + 1
    if tag_counts:
        print(f"\n{BOLD}{msg('stats_categories_header')}{RESET}")
        for tag, count in sorted(tag_counts.items(), key=lambda x: -x[1]):
            print(f"  {tag}: {count}")

    lesson_fire_counts = {}
    for entry in entries:
        for lid in entry.get("lessons_matched", []):
            lesson_fire_counts[lid] = lesson_fire_counts.get(lid, 0) + 1
    if lesson_fire_counts:
        print(f"\n{BOLD}{msg('stats_top_triggers_header')}{RESET}")
        top5 = sorted(lesson_fire_counts.items(), key=lambda x: -x[1])[:5]
        for lid, count in top5:
            print(f"  {count:3d}x  {lid}")

    dated = [(l, l.get("created", "")) for l in lessons if l.get("created")]
    dated.sort(key=lambda x: x[1], reverse=True)
    if dated:
        print(f"\n{BOLD}{msg('stats_recently_added_header')}{RESET}")
        for lesson, created in dated[:5]:
            lid = lesson.get("id", "unknown")
            severity = lesson.get("severity", "info").upper()
            icon = "\U0001f534" if severity == "CRITICAL" else "\U0001f7e1" if severity == "WARNING" else "\U0001f535"
            print(f"  {icon} {created}  {lid}")

    return 0


def cmd_hook(args):
    """Install or uninstall brain guard as a Claude Code hook."""
    if not args or args[0] not in ("install", "uninstall", "status"):
        print(msg("hook_error_invalid"), file=sys.stderr)
        print(msg("hook_error_invalid_desc"), file=sys.stderr)
        print(msg("hook_error_invalid_usage"), file=sys.stderr)
        return 1

    settings_path = Path.home() / ".claude" / "settings.json"
    brain_cmd = str(Path(__file__).parent / "brain")

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
            print(f"\u26aa {msg('hook_status_not_installed_no_settings')}")
            return 0
        settings = json.loads(settings_path.read_text())
        hooks = settings.get("hooks", {}).get("PreToolUse", [])
        installed = any("brain guard" in json.dumps(h) for h in hooks)
        print(f"{'\U0001f7e2 ' + msg('hook_status_installed') if installed else '\u26aa ' + msg('hook_status_not_installed')}")
        return 0

    if args[0] == "uninstall":
        if not settings_path.exists():
            print(msg("hook_uninstall_no_settings"))
            return 0
        settings = json.loads(settings_path.read_text())
        hooks = settings.get("hooks", {}).get("PreToolUse", [])
        new_hooks = [h for h in hooks if "brain guard" not in json.dumps(h)]
        if len(new_hooks) == len(hooks):
            print(f"\u26aa {msg('hook_uninstall_not_found')}")
            return 0
        settings["hooks"]["PreToolUse"] = new_hooks
        settings_path.write_text(json.dumps(settings, indent=2, ensure_ascii=False) + "\n")
        print(f"\U0001f5d1\ufe0f  {msg('hook_uninstall_success')}")
        return 0

    # --- install ---
    if not settings_path.exists():
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        settings = {"hooks": {"PreToolUse": [hook_entry]}}
        settings_path.write_text(json.dumps(settings, indent=2, ensure_ascii=False) + "\n")
        print(f"\U0001f9e0 {msg('hook_install_created', path=settings_path)}")
        return 0

    settings = json.loads(settings_path.read_text())

    existing_hooks = settings.get("hooks", {}).get("PreToolUse", [])
    if any("brain guard" in json.dumps(h) for h in existing_hooks):
        print(f"\U0001f7e2 {msg('hook_install_already')}")
        return 0

    if "hooks" not in settings:
        settings["hooks"] = {}
    if "PreToolUse" not in settings["hooks"]:
        settings["hooks"]["PreToolUse"] = []

    settings["hooks"]["PreToolUse"].append(hook_entry)
    settings_path.write_text(json.dumps(settings, indent=2, ensure_ascii=False) + "\n")
    print(f"\U0001f9e0 {msg('hook_install_success')}")
    print(msg("hook_install_description"))
    print(msg("hook_install_verify_hint"))
    return 0


def cmd_export(args):
    """Export lessons to Markdown, JSON, or HTML format."""
    load_plugins()
    fmt = "md"
    output_file = None

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

    builtin_formats = ("md", "json", "markdown", "html")
    if fmt not in builtin_formats and fmt not in REGISTRY.exporters:
        supported = ", ".join(["md", "json", "html"] + list(REGISTRY.exporters.keys()))
        print(msg("export_error_unknown_format", fmt=fmt), file=sys.stderr)
        print(msg("export_error_unknown_format_detail", formats=supported), file=sys.stderr)
        print(msg("export_error_unknown_format_usage"), file=sys.stderr)
        return 1

    lessons = load_all_lessons()

    # Plugin exporters
    if fmt in REGISTRY.exporters:
        content = REGISTRY.exporters[fmt](lessons, output_file)
        if output_file and content:
            print(f"\u2705 {msg('export_success', count=len(lessons), path=output_file)}")
        elif content:
            print(content)
        return 0

    if fmt in ("md", "markdown"):
        lines = [msg("export_md_title"), ""]
        lines.append(msg("export_md_count", count=len(lessons), date=datetime.date.today().isoformat()))
        lines.append("")

        for lesson in lessons:
            severity = lesson.get("severity", "info").upper()
            lid = lesson.get("id", "unknown")
            icon = "\U0001f534" if severity == "CRITICAL" else "\U0001f7e1" if severity == "WARNING" else "\U0001f535"

            lines.append(f"## {icon} {lid}")
            lines.append(msg("export_md_severity_label", severity=severity))

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
                lines.append(f"{msg('export_md_triggers_label')}`{'`, `'.join(patterns)}`")

            tags = lesson.get("tags", [])
            if tags:
                tag_list = tags if isinstance(tags, list) else [tags]
                lines.append(msg("export_md_tags_label", tags=", ".join(tag_list)))

            lines.append("")
            lines.append("---")
            lines.append("")

        content = "\n".join(lines)

    elif fmt == "html":
        content = _export_html(lessons)

    else:
        # JSON export
        clean = []
        for lesson in lessons:
            entry = {k: v for k, v in lesson.items() if not k.startswith("_")}
            clean.append(entry)
        content = json.dumps(clean, indent=2, ensure_ascii=False)

    if output_file:
        Path(output_file).write_text(content)
        print(f"\u2705 {msg('export_success', count=len(lessons), path=output_file)}")
    else:
        print(content)

    return 0


def _export_html(lessons: list) -> str:
    """Generate standalone HTML report with inline CSS."""
    today = datetime.date.today().isoformat()
    severity_colors = {
        "CRITICAL": "#dc3545",
        "WARNING": "#ffc107",
        "INFO": "#17a2b8",
    }

    lesson_cards = []
    for lesson in lessons:
        severity = lesson.get("severity", "info").upper()
        lid = lesson.get("id", "unknown")
        color = severity_colors.get(severity, "#17a2b8")
        text = _html_escape(lesson.get("lesson", "")).replace("\n", "<br>")
        checklist = lesson.get("checklist", [])
        patterns = lesson.get("trigger_patterns", [])
        tags = lesson.get("tags", [])
        if isinstance(tags, str):
            tags = [tags]

        checklist_html = ""
        if checklist:
            items = "".join(f"<li>{_html_escape(item)}</li>" for item in checklist)
            checklist_html = f'<ul class="checklist">{items}</ul>'

        patterns_html = ""
        if patterns:
            codes = ", ".join(f"<code>{_html_escape(p)}</code>" for p in patterns)
            patterns_html = f'<div class="triggers">Triggers: {codes}</div>'

        tags_html = ""
        if tags:
            spans = " ".join(f'<span class="tag">{_html_escape(t)}</span>' for t in tags)
            tags_html = f'<div class="tags">{spans}</div>'

        lesson_cards.append(f'''<div class="card">
  <div class="card-header" style="border-left: 4px solid {color};">
    <span class="severity" style="color: {color};">{severity}</span>
    <span class="lid">{_html_escape(lid)}</span>
  </div>
  <div class="card-body">
    <p>{text}</p>
    {checklist_html}
    {patterns_html}
    {tags_html}
  </div>
</div>''')

    cards_html = "\n".join(lesson_cards)

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Shared Brain &mdash; Lesson Export</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
         background: #f5f5f5; color: #333; padding: 2rem; max-width: 900px; margin: 0 auto; }}
  h1 {{ font-size: 1.8rem; margin-bottom: 0.5rem; }}
  .subtitle {{ color: #666; margin-bottom: 2rem; }}
  .card {{ background: #fff; border-radius: 8px; margin-bottom: 1rem;
           box-shadow: 0 1px 3px rgba(0,0,0,0.1); overflow: hidden; }}
  .card-header {{ padding: 0.75rem 1rem; display: flex; align-items: center; gap: 0.75rem; }}
  .severity {{ font-weight: 700; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em; }}
  .lid {{ font-weight: 600; font-size: 1rem; }}
  .card-body {{ padding: 0.75rem 1rem 1rem; }}
  .card-body p {{ line-height: 1.6; margin-bottom: 0.5rem; }}
  .checklist {{ list-style: none; padding: 0; margin: 0.5rem 0; }}
  .checklist li {{ padding: 0.25rem 0; padding-left: 1.5rem; position: relative; }}
  .checklist li::before {{ content: "\\2610"; position: absolute; left: 0; }}
  .triggers {{ font-size: 0.85rem; color: #555; margin-top: 0.5rem; }}
  .triggers code {{ background: #f0f0f0; padding: 0.1rem 0.4rem; border-radius: 3px; font-size: 0.8rem; }}
  .tags {{ margin-top: 0.5rem; }}
  .tag {{ display: inline-block; background: #e9ecef; color: #495057; padding: 0.15rem 0.5rem;
          border-radius: 3px; font-size: 0.8rem; margin-right: 0.25rem; }}
  footer {{ margin-top: 2rem; text-align: center; color: #999; font-size: 0.8rem; }}
</style>
</head>
<body>
<h1>&#129504; Shared Brain</h1>
<p class="subtitle">{len(lessons)} lessons exported on {today}</p>
{cards_html}
<footer>Generated by Shared Brain CLI &mdash; <a href="https://github.com/yurukusa/shared-brain">github.com/yurukusa/shared-brain</a></footer>
</body>
</html>'''


def _html_escape(text: str) -> str:
    """Minimal HTML escaping."""
    return (text
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;"))


def cmd_search(args):
    """Full-text search across lessons with highlighting and detail."""
    if not args:
        print(msg("search_error_no_term"), file=sys.stderr)
        print(msg("search_error_no_term_desc"), file=sys.stderr)
        print(msg("search_error_no_term_usage1"), file=sys.stderr)
        print(msg("search_error_no_term_usage2"), file=sys.stderr)
        print(msg("search_error_no_term_usage3"), file=sys.stderr)
        return 1

    tag_filter = None
    severity_filter = None
    keywords = []
    i = 0
    while i < len(args):
        if args[i] == "--tag" and i + 1 < len(args):
            tag_filter = args[i + 1].lower()
            i += 2
        elif args[i] == "--severity" and i + 1 < len(args):
            severity_filter = args[i + 1].lower()
            i += 2
        else:
            keywords.append(args[i])
            i += 1

    query = " ".join(keywords).lower() if keywords else ""
    lessons = load_all_lessons()
    results = []

    for lesson in lessons:
        if tag_filter:
            tags = lesson.get("tags", [])
            if isinstance(tags, str):
                tags = [tags]
            if not any(tag_filter in t.lower() for t in tags):
                continue

        if severity_filter:
            if lesson.get("severity", "info").lower() != severity_filter:
                continue

        if query:
            match_fields = []
            for field in ("id", "lesson", "tags", "trigger_patterns", "checklist"):
                val = lesson.get(field, "")
                text = json.dumps(val, ensure_ascii=False, default=str).lower() if not isinstance(val, str) else val.lower()
                if query in text:
                    match_fields.append(field)
            if not match_fields:
                continue
            results.append((lesson, match_fields))
        else:
            results.append((lesson, []))

    if not results:
        print(msg("search_no_results", query=query or tag_filter or severity_filter))
        return 0

    BOLD = "\033[1m"
    CYAN = "\033[1;36m"
    YELLOW = "\033[1;33m"
    RESET = "\033[0m"

    print(f"\U0001f50d {msg('search_result_count', count=len(results))}")
    for lesson, match_fields in results:
        severity = lesson.get("severity", "info").upper()
        lid = lesson.get("id", "unknown")
        icon = "\U0001f534" if severity == "CRITICAL" else "\U0001f7e1" if severity == "WARNING" else "\U0001f535"

        print(f"  {icon} {BOLD}{lid}{RESET}  [{severity}]")

        text = lesson.get("lesson", "")
        if text:
            for line in text.strip().split("\n")[:2]:
                print(f"     {line[:100]}")

        tags = lesson.get("tags", [])
        if tags:
            tag_list = tags if isinstance(tags, list) else [tags]
            print(f"     {CYAN}{msg('search_tags_label')}{RESET} {', '.join(tag_list)}")

        patterns = lesson.get("trigger_patterns", [])
        if patterns:
            print(f"     {CYAN}{msg('search_triggers_label')}{RESET} {', '.join(patterns[:3])}")

        if match_fields:
            print(f"     {YELLOW}{msg('search_matched_in_label')}{RESET} {', '.join(match_fields)}")

        print()

    return 0


def cmd_benchmark(args):
    """Run performance benchmark."""
    benchmark_script = Path(__file__).parent / "tests" / "benchmark.py"
    if not benchmark_script.exists():
        print(msg("benchmark_error_not_found"), file=sys.stderr)
        print(msg("benchmark_error_expected_at", path=benchmark_script), file=sys.stderr)
        print(msg("benchmark_error_hint"), file=sys.stderr)
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
{CYAN}\u2554{'═'*46}\u2557
\u2551         \U0001f9e0 Shared Brain Demo Mode            \u2551
\u2551                                              \u2551
\u2551  A sandbox with pre-loaded lessons and       \u2551
\u2551  audit data. Try every command risk-free.    \u2551
\u255a{'═'*46}\u255d{RESET}
""")

    demo_dir = Path(tempfile.mkdtemp(prefix="brain-demo-"))
    demo_lessons = demo_dir / "lessons"
    demo_lessons.mkdir()
    demo_audit = demo_dir / "audit"
    demo_audit.mkdir()

    original_brain_dir = BRAIN_DIR
    original_lessons = LESSONS_DIR
    original_audit = AUDIT_FILE

    _mod = sys.modules[__name__]
    original_builtin = BUILTIN_LESSONS
    _mod.BRAIN_DIR = demo_dir
    _mod.LESSONS_DIR = demo_lessons
    _mod.AUDIT_FILE = demo_dir / "audit.jsonl"
    _mod.BUILTIN_LESSONS = demo_dir / "no-builtins"

    try:
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
                "source": {"incident": "Zenn article overwrite \u2014 5 articles deleted by PUT without GET"},
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
                "lesson": "Always run tests before deploying to production.\nA passing CI pipeline is not enough \u2014 run tests locally too.",
                "checklist": ["Tests pass locally", "CI pipeline green", "Rollback plan exists"],
                "tags": ["deploy", "testing"],
            },
        ]

        for lesson in demo_lesson_data:
            dump_yaml(lesson, demo_lessons / f"{lesson['id']}.yaml")

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
        print(f"  \u2022 4 lessons (2 critical, 2 warning)")
        print(f"  \u2022 7 audit entries across 2 agents")
        print(f"  \u2022 Sandbox dir: {demo_dir}")
        print()
        print(f"{BOLD}Try these commands:{RESET}")
        print()
        print(f"  {CYAN}brain list{RESET}             \u2014 See all demo lessons")
        print(f"  {CYAN}brain guard \"curl -X PUT ...\"{RESET}  \u2014 Trigger a guard")
        print(f"  {CYAN}brain check \"PUT\"{RESET}      \u2014 Search lessons")
        print(f"  {CYAN}brain audit{RESET}             \u2014 View compliance report")
        print(f"  {CYAN}brain stats{RESET}             \u2014 Quick stats")
        print(f"  {CYAN}brain export --format md{RESET} \u2014 Export lessons")
        print()

        if args:
            subcmd = args[0]
            subargs = args[1:]
            if subcmd in COMMANDS:
                COMMANDS[subcmd](subargs)
            else:
                print(f"Unknown demo command: {subcmd}")
        else:
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

    def pause(prompt_msg="Press Enter to continue..."):
        if sys.stdin.isatty():
            input(f"\n{BOLD}{prompt_msg}{RESET}")
        else:
            print()

    print(f"""
{CYAN}\u2554{'═'*46}\u2557
\u2551         \U0001f9e0 Shared Brain Tutorial             \u2551
\u2551                                              \u2551
\u2551  Learn how to create lessons, guard commands,\u2551
\u2551  and audit compliance \u2014 in 3 steps.          \u2551
\u255a{'═'*46}\u255d{RESET}
""")

    # --- Step 1: Create a tutorial lesson ---
    step(1, "Create a lesson")

    tutorial_lesson_id = "tutorial-example"
    tutorial_file = LESSONS_DIR / f"{tutorial_lesson_id}.yaml"

    print(f"""Lessons teach agents what {RED}not{RESET} to do.
Each lesson has:
  \u2022 {BOLD}trigger_patterns{RESET} \u2014 regex patterns that match risky commands
  \u2022 {BOLD}severity{RESET} \u2014 critical, warning, or info
  \u2022 {BOLD}checklist{RESET} \u2014 steps to verify before proceeding

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
            "incident": "Tutorial example \u2014 common agent mistake",
        },
        "tags": ["filesystem", "destructive", "tutorial"],
    }

    dump_yaml(lesson_data, tutorial_file)
    print(f"""{GREEN}\u2705 Created lesson:{RESET} {tutorial_lesson_id}
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

    guard("rm -rf /tmp/old-data", agent="tutorial-user", auto_confirm=True)

    print(f"""
{GREEN}The guard matched the command against our lesson and showed
the warning with a checklist.{RESET}

In real usage:
  \u2022 As a {BOLD}CLI command{RESET}: the user sees this and types y/N
  \u2022 As a {BOLD}Claude Code hook{RESET}: it fires automatically before
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

  1. {BOLD}brain write{RESET}     \u2014 Create lessons from incidents
  2. {BOLD}brain guard{RESET}     \u2014 Check commands before execution
  3. {BOLD}brain audit{RESET}     \u2014 Prove compliance with data

{BOLD}Next steps:{RESET}
  \u2022 Run {CYAN}brain list{RESET} to see all built-in lessons
  \u2022 Run {CYAN}brain hook install{RESET} to auto-guard Claude Code
  \u2022 Run {CYAN}brain write{RESET} to create your own lesson
""")

    if tutorial_file.exists():
        tutorial_file.unlink()
        print(f"  (Tutorial lesson cleaned up)")

    return 0


def cmd_help(args=None):
    """Show help."""
    print(f"\U0001f9e0 {msg('help_text')}")
    return 0


# --- Main ---

COMMANDS = {
    "write": cmd_write,
    "guard": cmd_guard,
    "check": cmd_check,
    "search": cmd_search,
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
        print(msg("main_error_unknown_command", cmd=cmd), file=sys.stderr)
        print(msg("main_error_available_commands"), file=sys.stderr)
        print(msg("main_error_help_hint"), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main() or 0)
