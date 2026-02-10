"""
Shared Brain CLI - English message catalog (default/fallback).

Placeholders ({lid}, {dest}, etc.) are substituted at runtime via str.format().
ANSI color codes are NOT included here — the display logic adds them.
"""

MESSAGES = {

    # =========================================================================
    # Common / Utility
    # =========================================================================

    "aborted": "Aborted.",
    "proceed_prompt": "Proceed? [y/N] ",
    "proceed_auto_confirmed": "Proceed? [y/N] y  (auto-confirmed)",
    "non_interactive_warning": "Running in non-interactive mode. Proceeding with caution.",
    "press_enter": "Press Enter to continue...",

    # =========================================================================
    # Warnings (stderr)
    # =========================================================================

    "warn_load_failed": "Warning: Failed to load {path}: {error}",
    "warn_audit_read_failed": "Warning: Could not read audit file: {error}",
    "warn_audit_corrupt_line": "Warning: Skipping corrupt audit entry on line {line_num}",
    "warn_regex_timeout": "Warning: Regex pattern timed out (possible ReDoS): {pattern}",

    # =========================================================================
    # brain write
    # =========================================================================

    "write_error_file_not_found": "Error: File not found: {src}",
    "write_error_file_not_found_detail": "  The YAML file '{src}' does not exist.",
    "write_error_file_not_found_hint": "  Create it first, or use 'brain write' to add a lesson interactively.",
    "write_error_invalid_id": "Error: Invalid lesson ID '{raw_lid}'.",
    "write_error_invalid_id_detail": "  Lesson IDs must contain only word characters and hyphens.",
    "write_error_invalid_id_path_sep": "  Path separators (/, \\) and '..' are not allowed.",
    "write_error_invalid_id_short": "Error: Invalid lesson ID '{raw_lid}'. Use only word characters and hyphens.",
    "write_error_path_traversal": "Error: Path traversal detected in lesson ID '{raw_lid}'.",
    "write_success_from_file": "Lesson '{lid}' written to {dest}",
    "write_success_interactive": "\nLesson '{lid}' saved to {dest}",
    "write_header": "New Lesson",
    "write_prompt_id": "ID (short, kebab-case): ",
    "write_prompt_severity": "Severity (critical/warning/info) [warning]: ",
    "write_prompt_lesson": "Lesson (what should agents know?): ",
    "write_prompt_trigger_intro": "Trigger patterns (regex, empty line to finish):",
    "write_prompt_trigger": "  pattern> ",
    "write_prompt_checklist_intro": "Checklist items (empty line to finish):",
    "write_prompt_checklist": "  check> ",

    # =========================================================================
    # brain guard
    # =========================================================================

    "guard_error_no_command": "Error: No command specified.",
    "guard_error_no_command_desc": "  brain guard checks a command against known lessons before execution.",
    "guard_error_no_command_usage": '  Usage: brain guard "curl -X PUT https://api.example.com/articles/123"',
    "guard_severity_lesson": "  {severity} LESSON: {lid}",
    "guard_violated_count": "   (violated {count}x, last: {last})",
    "guard_no_description": "No description available.",
    "guard_checklist_header": "Checklist:",
    "guard_source_label": "   Source: {incident}",

    # =========================================================================
    # brain check
    # =========================================================================

    "check_error_no_keyword": "Error: No keyword specified.",
    "check_error_no_keyword_desc": "  brain check searches all lessons by keyword.",
    "check_error_no_keyword_usage": '  Usage: brain check "PUT" or brain check "api safety"',
    "check_no_results": "No lessons found for '{keyword}'",
    "check_found": "Found {count} lesson(s) matching '{keyword}':\n",
    "check_no_description": "(no description)",
    "check_violated_count": "     Violated {count} time(s)",

    # =========================================================================
    # brain list
    # =========================================================================

    "list_empty": "No lessons found. Use 'brain write' to add one.",
    "list_header": "{count} lesson(s):\n",
    "list_builtin_label": " (built-in)",
    "list_no_description": "(no description)",
    "list_triggers_label": "     Triggers: {triggers}",
    "list_violated_label": "     Violated {count}x",

    # =========================================================================
    # brain audit
    # =========================================================================

    "audit_empty": "No audit entries yet.",
    "audit_header": "Audit Report",
    "audit_total_checks": "Total checks: {count}",
    "audit_followed": "Followed:     {count}",
    "audit_blocked": "Blocked:      {count}",
    "audit_compliance": "Compliance:   {rate:.0f}%",
    "audit_per_lesson": "Per-lesson breakdown:",
    "audit_last_entries": "\nLast {count} entries:",

    # =========================================================================
    # brain stats
    # =========================================================================

    "stats_header": "Shared Brain Stats",
    "stats_lessons": "Lessons:       {total} ({critical} critical)",
    "stats_violations": "Violations:    {count} (historical)",
    "stats_guard_fires": "Guard fires:   {count}",
    "stats_proceeded": "Proceeded:     {count}",
    "stats_aborted": "Aborted:       {count}",
    "stats_prevention": "Prevention:    {rate:.0f}% (mistakes caught)",
    "stats_severity_header": "Severity Breakdown:",
    "stats_severity_critical": "  Critical: {count}",
    "stats_severity_warning": "  Warning:  {count}",
    "stats_severity_info": "  Info:     {count}",
    "stats_categories_header": "Categories (by tags):",
    "stats_top_triggers_header": "Top 5 Guard Triggers:",
    "stats_recently_added_header": "Recently Added (last 5):",

    # =========================================================================
    # brain hook
    # =========================================================================

    "hook_error_invalid": "Error: Missing or invalid hook subcommand.",
    "hook_error_invalid_desc": "  brain hook manages the Claude Code PreToolUse integration.",
    "hook_error_invalid_usage": "  Usage: brain hook install | brain hook uninstall | brain hook status",
    "hook_status_not_installed_no_settings": "Not installed (settings.json not found)",
    "hook_status_installed": "Installed",
    "hook_status_not_installed": "Not installed",
    "hook_uninstall_no_settings": "Nothing to uninstall (settings.json not found)",
    "hook_uninstall_not_found": "Brain guard hook not found in settings",
    "hook_uninstall_success": "Brain guard hook removed from Claude Code",
    "hook_install_created": "Brain guard installed! (created {path})",
    "hook_install_already": "Brain guard hook already installed",
    "hook_install_success": "Brain guard installed into Claude Code!",
    "hook_install_description": "   Every Bash command will now be checked against lessons.",
    "hook_install_verify_hint": "   Run 'brain hook status' to verify.",

    # =========================================================================
    # brain export
    # =========================================================================

    "export_error_unknown_format": "Error: Unknown format '{fmt}'.",
    "export_error_unknown_format_detail": "  Supported formats: {formats}.",
    "export_error_unknown_format_usage": "  Usage: brain export --format md --output lessons.md",
    "export_md_title": "# Shared Brain \u2014 Exported Lessons",
    "export_md_count": "*{count} lessons exported on {date}*",
    "export_md_severity_label": "**Severity:** {severity}",
    "export_md_triggers_label": "**Triggers:** ",
    "export_md_tags_label": "**Tags:** {tags}",
    "export_success": "Exported {count} lessons to {path}",

    # =========================================================================
    # brain search
    # =========================================================================

    "search_error_no_term": "Error: No search term specified.",
    "search_error_no_term_desc": "  brain search finds lessons matching keywords.",
    "search_error_no_term_usage1": '  Usage: brain search "CDP"',
    "search_error_no_term_usage2": "         brain search --tag api",
    "search_error_no_term_usage3": '         brain search --severity critical "PUT"',
    "search_no_results": "No lessons found for '{query}'",
    "search_result_count": "{count} result(s):\n",
    "search_tags_label": "Tags:",
    "search_triggers_label": "Triggers:",
    "search_matched_in_label": "Matched in:",

    # =========================================================================
    # brain benchmark
    # =========================================================================

    "benchmark_error_not_found": "Error: Benchmark script not found.",
    "benchmark_error_expected_at": "  Expected at: {path}",
    "benchmark_error_hint": "  This file ships with the source repo. Try: git clone && cd shared-brain",

    # =========================================================================
    # brain help
    # =========================================================================

    "help_text": """Shared Brain - AI agents that learn from each other's mistakes

Usage:
  brain write                 Add a new lesson interactively
  brain write -f <file.yaml>  Add a lesson from a YAML file
  brain guard <command>       Check command against known lessons
  brain check <keyword>       Search lessons by keyword
  brain search <term>         Full-text search with highlighting
  brain search --tag <tag>    Filter lessons by tag
  brain search --severity <s> Filter by severity level
  brain list                  List all lessons
  brain audit [--json]        Show compliance report
  brain stats                 Quick stats summary
  brain stats --verbose       Detailed breakdown with categories & top triggers
  brain export [--format md|json|html] [--output file]
                              Export lessons for other projects
  brain hook install          Auto-install guard as Claude Code hook
  brain hook uninstall        Remove brain guard hook
  brain hook status           Check if hook is installed
  brain tutorial              Interactive walkthrough for new users

Environment:
  BRAIN_HOME    Override brain directory (default: ~/.brain)
  BRAIN_AGENT   Set agent name for audit logging
  BRAIN_LANG    Set language (e.g., ja, en)

Examples:
  brain guard "curl -X PUT https://api.example.com/articles/123"
  brain check "api safety"
  brain write -f my-lesson.yaml
  brain export --format json --output lessons.json
""",

    # =========================================================================
    # main
    # =========================================================================

    "main_error_unknown_command": "Error: Unknown command '{cmd}'.",
    "main_error_available_commands": "  Available commands: write, guard, check, search, list, audit, stats, export, hook, tutorial, benchmark",
    "main_error_help_hint": "  Run 'brain help' for detailed usage.",
}
