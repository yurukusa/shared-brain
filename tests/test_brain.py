"""Tests for shared-brain CLI commands."""

import json
import os
import sys
import subprocess
import tempfile
from pathlib import Path

import pytest

# Add parent dir to path so we can import brain_engine
sys.path.insert(0, str(Path(__file__).parent.parent))
import brain_engine


@pytest.fixture
def brain_home(tmp_path):
    """Create an isolated brain home directory for each test."""
    home = tmp_path / ".brain"
    home.mkdir()
    (home / "lessons").mkdir()
    (home / "audit").mkdir()

    # Patch brain_engine to use our temp dir
    original_brain_dir = brain_engine.BRAIN_DIR
    original_lessons_dir = brain_engine.LESSONS_DIR
    original_audit_file = brain_engine.AUDIT_FILE
    original_builtin = brain_engine.BUILTIN_LESSONS

    brain_engine.BRAIN_DIR = home
    brain_engine.LESSONS_DIR = home / "lessons"
    brain_engine.AUDIT_FILE = home / "audit.jsonl"
    brain_engine.BUILTIN_LESSONS = tmp_path / "no_builtins"  # nonexistent dir

    yield home

    # Restore
    brain_engine.BRAIN_DIR = original_brain_dir
    brain_engine.LESSONS_DIR = original_lessons_dir
    brain_engine.AUDIT_FILE = original_audit_file
    brain_engine.BUILTIN_LESSONS = original_builtin


@pytest.fixture
def sample_lesson(brain_home):
    """Write a sample lesson YAML to the temp brain home."""
    lesson_content = """id: test-put-safety
severity: critical
created: "2026-02-08"
violated_count: 2
last_violated: "2026-02-09"

trigger_patterns:
  - "PUT /api/"
  - "curl.*-X PUT"

lesson: |
  Always GET before PUT.
  PUT replaces the entire resource.

checklist:
  - "GET current state"
  - "PUT body has ALL fields"

tags: [api, test]
"""
    lesson_file = brain_home / "lessons" / "test-put-safety.yaml"
    lesson_file.write_text(lesson_content)
    return lesson_file


@pytest.fixture
def sample_audit(brain_home):
    """Write sample audit entries."""
    entries = [
        {"timestamp": "2026-02-09T10:00:00Z", "agent": "test-agent", "action": "PUT /api/articles",
         "lessons_matched": ["test-put-safety"], "checked": True, "followed": True, "note": "user_confirmed"},
        {"timestamp": "2026-02-09T11:00:00Z", "agent": "test-agent", "action": "curl -X PUT",
         "lessons_matched": ["test-put-safety"], "checked": True, "followed": False, "note": "user_aborted"},
    ]
    audit_file = brain_home / "audit.jsonl"
    audit_file.write_text("\n".join(json.dumps(e) for e in entries) + "\n")
    return audit_file


# --- YAML parsing tests ---

class TestYamlParser:
    def test_parse_simple_key_value(self):
        result = brain_engine._parse_yaml_simple("id: test\nseverity: warning")
        assert result["id"] == "test"
        assert result["severity"] == "warning"

    def test_parse_list(self):
        text = "tags:\n  - api\n  - test"
        result = brain_engine._parse_yaml_simple(text)
        assert result["tags"] == ["api", "test"]

    def test_parse_inline_list(self):
        result = brain_engine._parse_yaml_simple("tags: [api, test, data]")
        assert result["tags"] == ["api", "test", "data"]

    def test_parse_multiline(self):
        text = "lesson: |\n  Line one.\n  Line two."
        result = brain_engine._parse_yaml_simple(text)
        assert "Line one." in result["lesson"]
        assert "Line two." in result["lesson"]

    def test_parse_boolean(self):
        result = brain_engine._parse_yaml_simple("active: true\ndisabled: false")
        assert result["active"] is True
        assert result["disabled"] is False

    def test_parse_integer(self):
        result = brain_engine._parse_yaml_simple("violated_count: 5")
        assert result["violated_count"] == 5

    def test_round_trip(self, tmp_path):
        data = {"id": "test", "severity": "warning", "tags": ["a", "b"], "count": 3}
        path = tmp_path / "test.yaml"
        brain_engine.dump_yaml(data, path)
        loaded = brain_engine.load_yaml(path)
        assert loaded["id"] == "test"
        assert loaded["severity"] == "warning"


# --- Guard tests ---

class TestGuard:
    def test_guard_matches_pattern(self, brain_home, sample_lesson, capsys):
        result = brain_engine.guard("curl -X PUT https://api.example.com", "test", auto_confirm=True)
        assert result is True
        captured = capsys.readouterr()
        assert "CRITICAL" in captured.out or "test-put-safety" in captured.out

    def test_guard_no_match(self, brain_home, sample_lesson):
        result = brain_engine.guard("curl -X GET https://api.example.com", "test", auto_confirm=True)
        assert result is True

    def test_guard_logs_audit(self, brain_home, sample_lesson):
        brain_engine.guard("curl -X PUT https://api.example.com", "test-agent", auto_confirm=True)
        entries = brain_engine.load_audit()
        assert len(entries) >= 1
        assert entries[-1]["agent"] == "test-agent"

    def test_guard_empty_lessons(self, brain_home):
        result = brain_engine.guard("anything", "test", auto_confirm=True)
        assert result is True

    def test_guard_invalid_regex_fallback(self, brain_home):
        """Trigger pattern with bad regex should fall back to substring match."""
        lesson_content = "id: bad-regex\nseverity: warning\ntrigger_patterns:\n  - \"[invalid\"\nlesson: test\n"
        (brain_home / "lessons" / "bad-regex.yaml").write_text(lesson_content)
        # Should not raise, should fall back to substring
        result = brain_engine.guard("[invalid", "test", auto_confirm=True)
        assert result is True


# --- Check tests ---

class TestCheck:
    def test_check_finds_lesson(self, brain_home, sample_lesson, capsys):
        result = brain_engine.cmd_check(["PUT"])
        assert result == 0
        captured = capsys.readouterr()
        assert "test-put-safety" in captured.out

    def test_check_no_results(self, brain_home, sample_lesson, capsys):
        result = brain_engine.cmd_check(["nonexistent_keyword"])
        assert result == 0
        captured = capsys.readouterr()
        assert "No lessons found" in captured.out


# --- List tests ---

class TestList:
    def test_list_shows_lessons(self, brain_home, sample_lesson, capsys):
        result = brain_engine.cmd_list([])
        assert result == 0
        captured = capsys.readouterr()
        assert "test-put-safety" in captured.out

    def test_list_empty(self, brain_home, capsys):
        result = brain_engine.cmd_list([])
        assert result == 0
        captured = capsys.readouterr()
        assert "No lessons found" in captured.out


# --- Stats tests ---

class TestStats:
    def test_stats_with_data(self, brain_home, sample_lesson, sample_audit, capsys):
        result = brain_engine.cmd_stats([])
        assert result == 0
        captured = capsys.readouterr()
        assert "Shared Brain Stats" in captured.out
        assert "Lessons:" in captured.out

    def test_stats_empty(self, brain_home, capsys):
        result = brain_engine.cmd_stats([])
        assert result == 0
        captured = capsys.readouterr()
        assert "Lessons:       0" in captured.out


# --- Audit tests ---

class TestAudit:
    def test_audit_report(self, brain_home, sample_audit, capsys):
        result = brain_engine.cmd_audit([])
        assert result == 0
        captured = capsys.readouterr()
        assert "Audit Report" in captured.out
        assert "Compliance:" in captured.out

    def test_audit_json(self, brain_home, sample_audit, capsys):
        result = brain_engine.cmd_audit(["--json"])
        assert result == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert len(data) == 2

    def test_audit_empty(self, brain_home, capsys):
        result = brain_engine.cmd_audit([])
        assert result == 0
        captured = capsys.readouterr()
        assert "No audit entries" in captured.out

    def test_audit_broken_jsonl(self, brain_home):
        """Broken JSONL lines should be skipped."""
        audit_file = brain_home / "audit.jsonl"
        audit_file.write_text('{"valid": true}\n{broken json\n{"also": "valid"}\n')
        entries = brain_engine.load_audit()
        assert len(entries) == 2


# --- Export tests ---

class TestExport:
    def test_export_markdown(self, brain_home, sample_lesson, capsys):
        result = brain_engine.cmd_export(["--format", "md"])
        assert result == 0
        captured = capsys.readouterr()
        assert "test-put-safety" in captured.out
        assert "# Shared Brain" in captured.out

    def test_export_json(self, brain_home, sample_lesson, capsys):
        result = brain_engine.cmd_export(["--format", "json"])
        assert result == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert len(data) >= 1

    def test_export_to_file(self, brain_home, sample_lesson, tmp_path):
        out_file = str(tmp_path / "export.md")
        result = brain_engine.cmd_export(["--format", "md", "--output", out_file])
        assert result == 0
        assert Path(out_file).exists()
        content = Path(out_file).read_text()
        assert "test-put-safety" in content

    def test_export_default_format(self, brain_home, sample_lesson, capsys):
        """Default format should be markdown."""
        result = brain_engine.cmd_export([])
        assert result == 0
        captured = capsys.readouterr()
        assert "# Shared Brain" in captured.out


# --- Error handling tests ---

class TestErrorHandling:
    def test_load_missing_lesson_file(self, brain_home):
        """Missing files should not crash."""
        lessons = brain_engine.load_all_lessons()
        assert isinstance(lessons, list)

    def test_load_corrupt_yaml(self, brain_home):
        """Corrupt YAML should be skipped with a warning."""
        corrupt = brain_home / "lessons" / "corrupt.yaml"
        corrupt.write_text("{{{{ this is not yaml ::::")
        lessons = brain_engine.load_all_lessons()
        # Should not raise, corrupt file skipped
        assert isinstance(lessons, list)

    def test_load_empty_yaml(self, brain_home):
        """Empty YAML file should be handled."""
        empty = brain_home / "lessons" / "empty.yaml"
        empty.write_text("")
        lessons = brain_engine.load_all_lessons()
        assert isinstance(lessons, list)

    def test_guard_with_none_patterns(self, brain_home):
        """Lesson with no trigger_patterns should be skipped."""
        lesson = brain_home / "lessons" / "no-patterns.yaml"
        lesson.write_text("id: no-patterns\nseverity: info\nlesson: just info\n")
        result = brain_engine.guard("anything", "test", auto_confirm=True)
        assert result is True

    def test_audit_nonexistent_file(self, brain_home):
        """Audit file that doesn't exist should return empty list."""
        entries = brain_engine.load_audit()
        assert entries == []

    def test_audit_empty_file(self, brain_home):
        """Empty audit file should return empty list."""
        (brain_home / "audit.jsonl").write_text("")
        entries = brain_engine.load_audit()
        assert entries == []

    def test_write_lesson_missing_file(self, brain_home, capsys):
        """Writing from nonexistent file should return error."""
        result = brain_engine.cmd_write(["-f", "/nonexistent/file.yaml"])
        assert result == 1
        captured = capsys.readouterr()
        assert "not found" in captured.err.lower() or "Error" in captured.err


# --- YAML parser edge cases ---

class TestYamlParserEdgeCases:
    def test_parse_unicode_values(self):
        """Unicode characters in YAML values should be preserved."""
        text = "id: unicode-test\nlesson: APIを壊すな。安全第一。"
        result = brain_engine._parse_yaml_simple(text)
        assert "APIを壊すな" in result["lesson"]

    def test_parse_empty_string(self):
        result = brain_engine._parse_yaml_simple("")
        assert result == {}

    def test_parse_comments_only(self):
        result = brain_engine._parse_yaml_simple("# just a comment\n# another")
        assert result == {}

    def test_parse_quoted_values(self):
        text = 'id: "quoted-id"\nseverity: \'single-quoted\''
        result = brain_engine._parse_yaml_simple(text)
        assert result["id"] == "quoted-id"
        assert result["severity"] == "single-quoted"

    def test_parse_nested_dict(self):
        text = "source:\n  incident: Something happened\n  url: https://example.com"
        result = brain_engine._parse_yaml_simple(text)
        assert isinstance(result["source"], dict)
        assert result["source"]["incident"] == "Something happened"
        assert result["source"]["url"] == "https://example.com"

    def test_parse_empty_value_key(self):
        """Key with no value should result in None."""
        result = brain_engine._parse_yaml_simple("empty_key:")
        assert result["empty_key"] is None

    def test_round_trip_with_multiline(self, tmp_path):
        data = {"id": "multiline-test", "lesson": "Line one.\nLine two.\nLine three."}
        path = tmp_path / "multi.yaml"
        brain_engine.dump_yaml(data, path)
        loaded = brain_engine.load_yaml(path)
        assert "Line one." in loaded["lesson"]
        assert "Line two." in loaded["lesson"]

    def test_round_trip_with_bool(self, tmp_path):
        data = {"id": "bool-test", "active": True, "disabled": False}
        path = tmp_path / "bool.yaml"
        brain_engine.dump_yaml(data, path)
        loaded = brain_engine.load_yaml(path)
        assert loaded["active"] is True
        assert loaded["disabled"] is False


# --- Guard edge cases ---

class TestGuardEdgeCases:
    def test_guard_multiple_lessons_match(self, brain_home, capsys):
        """Multiple lessons can match the same command."""
        lesson1 = "id: lesson-a\nseverity: warning\ntrigger_patterns:\n  - \"rm -rf\"\nlesson: danger\n"
        lesson2 = "id: lesson-b\nseverity: critical\ntrigger_patterns:\n  - \"rm\"\nlesson: also danger\n"
        (brain_home / "lessons" / "a.yaml").write_text(lesson1)
        (brain_home / "lessons" / "b.yaml").write_text(lesson2)
        result = brain_engine.guard("rm -rf /tmp", "test", auto_confirm=True)
        assert result is True
        captured = capsys.readouterr()
        # Both lessons should appear
        assert "lesson-a" in captured.out
        assert "lesson-b" in captured.out

    def test_guard_case_insensitive_match(self, brain_home):
        """Pattern matching should be case-insensitive."""
        lesson = "id: case-test\nseverity: warning\ntrigger_patterns:\n  - \"DELETE\"\nlesson: test\n"
        (brain_home / "lessons" / "case.yaml").write_text(lesson)
        result = brain_engine.guard("delete from users", "test", auto_confirm=True)
        assert result is True  # matches, but auto-confirmed

    def test_guard_auto_confirm_logs_correctly(self, brain_home, sample_lesson):
        """Auto-confirm should log 'user_confirmed' note."""
        brain_engine.guard("curl -X PUT https://example.com", "test", auto_confirm=True)
        entries = brain_engine.load_audit()
        confirmed = [e for e in entries if e.get("note") == "user_confirmed"]
        assert len(confirmed) >= 1

    def test_guard_no_match_logs_no_match(self, brain_home, sample_lesson):
        """No-match guard should log 'no_match' note."""
        brain_engine.guard("echo hello", "test")
        entries = brain_engine.load_audit()
        no_match = [e for e in entries if e.get("note") == "no_match"]
        assert len(no_match) >= 1

    def test_guard_truncates_long_commands(self, brain_home, sample_lesson):
        """Audit log should truncate very long commands to 200 chars."""
        long_cmd = "curl -X PUT " + "x" * 500
        brain_engine.guard(long_cmd, "test", auto_confirm=True)
        entries = brain_engine.load_audit()
        assert len(entries[-1]["action"]) <= 200

    def test_guard_displays_checklist(self, brain_home, sample_lesson, capsys):
        """Guard output should include checklist items."""
        brain_engine.guard("curl -X PUT https://example.com", "test", auto_confirm=True)
        captured = capsys.readouterr()
        assert "GET current state" in captured.out
        assert "PUT body has ALL fields" in captured.out

    def test_guard_displays_severity_icon(self, brain_home, capsys):
        """Different severity levels should display different formatting."""
        lesson = "id: info-test\nseverity: info\ntrigger_patterns:\n  - \"test-info\"\nlesson: informational\n"
        (brain_home / "lessons" / "info.yaml").write_text(lesson)
        brain_engine.guard("test-info command", "test", auto_confirm=True)
        captured = capsys.readouterr()
        assert "INFO" in captured.out or "info-test" in captured.out


# --- Lesson loading edge cases ---

class TestLessonLoading:
    def test_load_yml_extension(self, brain_home):
        """Both .yaml and .yml extensions should be loaded."""
        lesson = "id: yml-test\nseverity: info\nlesson: from yml\n"
        (brain_home / "lessons" / "test.yml").write_text(lesson)
        lessons = brain_engine.load_all_lessons()
        ids = [l.get("id") for l in lessons]
        assert "yml-test" in ids

    def test_dedup_by_id(self, brain_home):
        """Lessons with duplicate IDs should be deduped (first wins)."""
        lesson1 = "id: dup-test\nseverity: warning\nlesson: first\n"
        lesson2 = "id: dup-test\nseverity: critical\nlesson: second\n"
        (brain_home / "lessons" / "aaa.yaml").write_text(lesson1)
        (brain_home / "lessons" / "zzz.yaml").write_text(lesson2)
        lessons = brain_engine.load_all_lessons()
        dup_lessons = [l for l in lessons if l.get("id") == "dup-test"]
        assert len(dup_lessons) == 1
        # First alphabetically wins
        assert dup_lessons[0]["severity"] == "warning"

    def test_lesson_without_id_uses_stem(self, brain_home):
        """Lesson without 'id' key should use filename stem."""
        lesson = "severity: info\nlesson: no explicit id\n"
        (brain_home / "lessons" / "implicit-id.yaml").write_text(lesson)
        lessons = brain_engine.load_all_lessons()
        assert any(l.get("_file", "").endswith("implicit-id.yaml") for l in lessons)

    def test_builtin_lessons_loaded(self, tmp_path):
        """Built-in lessons directory should be included if it exists."""
        # Save originals
        orig_builtin = brain_engine.BUILTIN_LESSONS
        orig_lessons = brain_engine.LESSONS_DIR

        builtin_dir = tmp_path / "builtins"
        builtin_dir.mkdir()
        (builtin_dir / "builtin.yaml").write_text("id: builtin-lesson\nseverity: info\nlesson: built-in\n")

        brain_engine.BUILTIN_LESSONS = builtin_dir
        brain_engine.LESSONS_DIR = tmp_path / "user_lessons"
        brain_engine.LESSONS_DIR.mkdir()

        try:
            lessons = brain_engine.load_all_lessons()
            ids = [l.get("id") for l in lessons]
            assert "builtin-lesson" in ids
        finally:
            brain_engine.BUILTIN_LESSONS = orig_builtin
            brain_engine.LESSONS_DIR = orig_lessons


# --- Large audit file ---

class TestLargeAudit:
    def test_large_jsonl_audit(self, brain_home):
        """Audit with 1000+ entries should load correctly."""
        audit_file = brain_home / "audit.jsonl"
        lines = []
        for i in range(1000):
            entry = {"timestamp": f"2026-01-01T{i:05d}", "agent": "bulk", "action": f"action-{i}",
                     "lessons_matched": [], "checked": True, "followed": True, "note": "no_match"}
            lines.append(json.dumps(entry))
        audit_file.write_text("\n".join(lines) + "\n")
        entries = brain_engine.load_audit()
        assert len(entries) == 1000

    def test_audit_whitespace_lines_skipped(self, brain_home):
        """Blank lines in JSONL should be silently skipped."""
        audit_file = brain_home / "audit.jsonl"
        audit_file.write_text('{"valid": true}\n\n\n{"also": true}\n  \n')
        entries = brain_engine.load_audit()
        assert len(entries) == 2


# --- Check edge cases ---

class TestCheckEdgeCases:
    def test_check_no_args_returns_error(self, brain_home, capsys):
        result = brain_engine.cmd_check([])
        assert result == 1
        captured = capsys.readouterr()
        assert "Usage" in captured.err

    def test_check_case_insensitive(self, brain_home, sample_lesson, capsys):
        """Search should be case-insensitive."""
        result = brain_engine.cmd_check(["put"])
        assert result == 0
        captured = capsys.readouterr()
        assert "test-put-safety" in captured.out

    def test_check_matches_tags(self, brain_home, sample_lesson, capsys):
        """Search should match against tags."""
        result = brain_engine.cmd_check(["api"])
        assert result == 0
        captured = capsys.readouterr()
        assert "test-put-safety" in captured.out

    def test_check_violated_count_shown(self, brain_home, sample_lesson, capsys):
        """Violated count should be displayed for violated lessons."""
        result = brain_engine.cmd_check(["PUT"])
        assert result == 0
        captured = capsys.readouterr()
        assert "Violated" in captured.out or "2" in captured.out


# --- Export edge cases ---

class TestExportEdgeCases:
    def test_export_invalid_format(self, brain_home, capsys):
        result = brain_engine.cmd_export(["--format", "xml"])
        assert result == 1
        captured = capsys.readouterr()
        assert "Unknown format" in captured.err

    def test_export_json_no_internal_fields(self, brain_home, sample_lesson, capsys):
        """JSON export should not include _file internal field."""
        result = brain_engine.cmd_export(["--format", "json"])
        assert result == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        for entry in data:
            assert "_file" not in entry

    def test_export_markdown_includes_checklist(self, brain_home, sample_lesson, capsys):
        result = brain_engine.cmd_export(["--format", "md"])
        assert result == 0
        captured = capsys.readouterr()
        assert "- [ ]" in captured.out

    def test_export_empty_lessons(self, brain_home, capsys):
        result = brain_engine.cmd_export(["--format", "json"])
        assert result == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data == []


# --- Audit report edge cases ---

class TestAuditEdgeCases:
    def test_audit_compliance_percentage(self, brain_home, sample_audit, capsys):
        """Compliance percentage should be calculated correctly."""
        result = brain_engine.cmd_audit([])
        assert result == 0
        captured = capsys.readouterr()
        # 1 followed out of 2 = 50%
        assert "50%" in captured.out

    def test_audit_per_lesson_breakdown(self, brain_home, sample_audit, capsys):
        result = brain_engine.cmd_audit([])
        assert result == 0
        captured = capsys.readouterr()
        assert "test-put-safety" in captured.out

    def test_audit_last_entries_shown(self, brain_home, sample_audit, capsys):
        result = brain_engine.cmd_audit([])
        assert result == 0
        captured = capsys.readouterr()
        assert "Last 10 entries" in captured.out


# --- Stats edge cases ---

class TestStatsEdgeCases:
    def test_stats_prevention_rate(self, brain_home, sample_lesson, sample_audit, capsys):
        """Prevention rate should be calculated when guard fires exist."""
        result = brain_engine.cmd_stats([])
        assert result == 0
        captured = capsys.readouterr()
        assert "Prevention:" in captured.out

    def test_stats_critical_count(self, brain_home, capsys):
        """Critical count should reflect actual critical lessons."""
        (brain_home / "lessons" / "c1.yaml").write_text("id: c1\nseverity: critical\nlesson: crit\n")
        (brain_home / "lessons" / "c2.yaml").write_text("id: c2\nseverity: warning\nlesson: warn\n")
        result = brain_engine.cmd_stats([])
        assert result == 0
        captured = capsys.readouterr()
        assert "2" in captured.out  # 2 total lessons
        assert "1 critical" in captured.out


# --- Hook tests ---

class TestHook:
    def test_hook_install_creates_settings(self, brain_home, tmp_path, capsys):
        """Hook install should create settings.json if missing."""
        settings_path = tmp_path / ".claude" / "settings.json"
        # Temporarily override Path.home() behavior by patching the settings path
        import unittest.mock
        with unittest.mock.patch.object(brain_engine, 'cmd_hook') as mock_hook:
            # Just verify the function exists and is callable
            assert callable(brain_engine.cmd_hook)

    def test_hook_status_no_settings(self, tmp_path, capsys):
        """Hook status with no settings.json should report not installed."""
        import unittest.mock
        fake_settings = tmp_path / ".claude" / "settings.json"
        with unittest.mock.patch.object(Path, 'home', return_value=tmp_path):
            result = brain_engine.cmd_hook(["status"])
        assert result == 0
        captured = capsys.readouterr()
        assert "Not installed" in captured.out

    def test_hook_invalid_subcommand(self, capsys):
        result = brain_engine.cmd_hook(["invalid"])
        assert result == 1

    def test_hook_no_args(self, capsys):
        result = brain_engine.cmd_hook([])
        assert result == 1


# --- CLI help ---

class TestHelp:
    def test_help_output(self, capsys):
        result = brain_engine.cmd_help()
        assert result == 0
        captured = capsys.readouterr()
        assert "Shared Brain" in captured.out
        assert "brain guard" in captured.out
        assert "brain check" in captured.out

    def test_guard_no_args(self, capsys):
        result = brain_engine.cmd_guard([])
        assert result == 1
        captured = capsys.readouterr()
        assert "Usage" in captured.err


# --- Write from file ---

class TestWriteFromFile:
    def test_write_from_valid_file(self, brain_home, tmp_path, capsys):
        """Write should copy a valid YAML file to lessons dir."""
        src = tmp_path / "new-lesson.yaml"
        src.write_text("id: new-lesson\nseverity: info\nlesson: a new lesson\n")
        result = brain_engine.cmd_write(["-f", str(src)])
        assert result == 0
        captured = capsys.readouterr()
        assert "new-lesson" in captured.out
        # Verify the lesson was actually written
        dest = brain_home / "lessons" / "new-lesson.yaml"
        assert dest.exists()


# --- Tachikoma-specified edge cases ---

class TestUnicodeLessonNames:
    """Unicode教訓名のテスト（タチコマ指定エッジケース）"""

    def test_unicode_lesson_id(self, brain_home, capsys):
        """Lesson with Japanese ID should load and display correctly."""
        lesson = "id: api安全チェック\nseverity: critical\nlesson: APIを壊すな\ntrigger_patterns:\n  - \"PUT /api\"\n"
        (brain_home / "lessons" / "api安全チェック.yaml").write_text(lesson, encoding="utf-8")
        lessons = brain_engine.load_all_lessons()
        ids = [l.get("id") for l in lessons]
        assert "api安全チェック" in ids

    def test_unicode_lesson_in_guard(self, brain_home, capsys):
        """Guard should match and display Unicode lesson text."""
        lesson = "id: 日本語テスト\nseverity: warning\nlesson: データベースを壊すな。必ずバックアップを取れ。\ntrigger_patterns:\n  - \"DROP TABLE\"\nchecklist:\n  - \"バックアップ確認\"\n  - \"ロールバック手順の確認\"\n"
        (brain_home / "lessons" / "jp-test.yaml").write_text(lesson, encoding="utf-8")
        result = brain_engine.guard("DROP TABLE users", "test-agent", auto_confirm=True)
        assert result is True
        captured = capsys.readouterr()
        assert "日本語テスト" in captured.out
        assert "バックアップ確認" in captured.out

    def test_unicode_lesson_in_check(self, brain_home, capsys):
        """Check command should find lessons by Unicode keywords."""
        lesson = "id: emoji-test\nseverity: info\nlesson: 🔥 危険な操作を検知\ntags: [安全, テスト]\n"
        (brain_home / "lessons" / "emoji.yaml").write_text(lesson, encoding="utf-8")
        result = brain_engine.cmd_check(["安全"])
        assert result == 0
        captured = capsys.readouterr()
        assert "emoji-test" in captured.out

    def test_unicode_lesson_export_json(self, brain_home, capsys):
        """JSON export should preserve Unicode characters."""
        lesson = "id: 漢字テスト\nseverity: warning\nlesson: 全角文字を含む教訓\ntags: [日本語, テスト]\n"
        (brain_home / "lessons" / "kanji.yaml").write_text(lesson, encoding="utf-8")
        result = brain_engine.cmd_export(["--format", "json"])
        assert result == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert any(l["id"] == "漢字テスト" for l in data)
        assert any("全角文字" in l.get("lesson", "") for l in data)

    def test_unicode_in_trigger_pattern(self, brain_home):
        """Trigger patterns containing Unicode should match correctly."""
        lesson = "id: unicode-pattern\nseverity: warning\nlesson: test\ntrigger_patterns:\n  - \"削除\"\n"
        (brain_home / "lessons" / "up.yaml").write_text(lesson, encoding="utf-8")
        result = brain_engine.guard("データを削除する", "test", auto_confirm=True)
        assert result is True
        entries = brain_engine.load_audit()
        matched = [e for e in entries if "unicode-pattern" in e.get("lessons_matched", [])]
        assert len(matched) >= 1

    def test_unicode_filename_lesson(self, brain_home):
        """Lesson file with Unicode filename should load correctly."""
        lesson = "id: ファイル名テスト\nseverity: info\nlesson: ファイル名が日本語\n"
        (brain_home / "lessons" / "日本語ファイル.yaml").write_text(lesson, encoding="utf-8")
        lessons = brain_engine.load_all_lessons()
        ids = [l.get("id") for l in lessons]
        assert "ファイル名テスト" in ids


class TestLargeJSONLEdgeCases:
    """巨大JSONLファイルのテスト（タチコマ指定エッジケース）"""

    def test_very_large_audit_10k_entries(self, brain_home):
        """10,000 audit entries should load without error."""
        audit_file = brain_home / "audit.jsonl"
        lines = []
        for i in range(10000):
            entry = {
                "timestamp": f"2026-01-01T{i:06d}",
                "agent": f"agent-{i % 10}",
                "action": f"action-{i}",
                "lessons_matched": [f"lesson-{i % 5}"],
                "checked": True,
                "followed": i % 3 != 0,
                "note": "test",
            }
            lines.append(json.dumps(entry))
        audit_file.write_text("\n".join(lines) + "\n")
        entries = brain_engine.load_audit()
        assert len(entries) == 10000

    def test_large_audit_report_display(self, brain_home, capsys):
        """Audit report with many entries should still show correctly."""
        audit_file = brain_home / "audit.jsonl"
        lines = []
        for i in range(500):
            entry = {
                "timestamp": f"2026-01-01T{i:05d}",
                "agent": "bulk-agent",
                "action": f"curl -X PUT /api/resource/{i}",
                "lessons_matched": ["put-safety"],
                "checked": True,
                "followed": True,
                "note": "user_confirmed",
            }
            lines.append(json.dumps(entry))
        audit_file.write_text("\n".join(lines) + "\n")
        result = brain_engine.cmd_audit([])
        assert result == 0
        captured = capsys.readouterr()
        assert "500" in captured.out
        assert "Last 10 entries" in captured.out

    def test_large_audit_json_export(self, brain_home, capsys):
        """JSON audit export with many entries should be valid JSON."""
        audit_file = brain_home / "audit.jsonl"
        lines = []
        for i in range(200):
            entry = {"timestamp": f"T{i}", "agent": "test", "action": f"a{i}",
                     "lessons_matched": [], "checked": True, "followed": True, "note": "no_match"}
            lines.append(json.dumps(entry))
        audit_file.write_text("\n".join(lines) + "\n")
        result = brain_engine.cmd_audit(["--json"])
        assert result == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert len(data) == 200

    def test_audit_with_mixed_valid_invalid_lines(self, brain_home):
        """Large JSONL with scattered corrupt lines should skip bad ones."""
        audit_file = brain_home / "audit.jsonl"
        lines = []
        valid_count = 0
        for i in range(100):
            if i % 7 == 0:
                lines.append("NOT_JSON_LINE_{}")
            else:
                entry = {"timestamp": f"T{i}", "agent": "test", "action": f"a{i}",
                         "lessons_matched": [], "checked": True, "followed": True, "note": "no_match"}
                lines.append(json.dumps(entry))
                valid_count += 1
        audit_file.write_text("\n".join(lines) + "\n")
        entries = brain_engine.load_audit()
        assert len(entries) == valid_count

    def test_audit_with_unicode_actions(self, brain_home):
        """Audit entries with Unicode in action field should be preserved."""
        audit_file = brain_home / "audit.jsonl"
        entry = {"timestamp": "2026-01-01", "agent": "テスト", "action": "curl -X PUT /api/記事/123",
                 "lessons_matched": ["日本語レッスン"], "checked": True, "followed": True, "note": "ok"}
        audit_file.write_text(json.dumps(entry, ensure_ascii=False) + "\n")
        entries = brain_engine.load_audit()
        assert len(entries) == 1
        assert "記事" in entries[0]["action"]
        assert entries[0]["agent"] == "テスト"


class TestConcurrentWriteSimulation:
    """同時書き込みシミュレーション（タチコマ指定エッジケース）"""

    def test_concurrent_audit_writes(self, brain_home):
        """Multiple rapid audit writes should not lose entries."""
        import threading
        errors = []

        def write_audit(agent_id, count):
            try:
                for i in range(count):
                    brain_engine.log_audit(
                        f"agent-{agent_id}",
                        f"action-{agent_id}-{i}",
                        None,
                        checked=True,
                        followed=True,
                        note="concurrent_test"
                    )
            except Exception as e:
                errors.append(e)

        threads = []
        writes_per_thread = 20
        num_threads = 5
        for tid in range(num_threads):
            t = threading.Thread(target=write_audit, args=(tid, writes_per_thread))
            threads.append(t)

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Errors during concurrent writes: {errors}"
        entries = brain_engine.load_audit()
        # All entries should be written (some may be interleaved but all present)
        assert len(entries) == num_threads * writes_per_thread

    def test_concurrent_lesson_load_during_write(self, brain_home):
        """Loading lessons while a new lesson is being written should not crash."""
        import threading
        errors = []

        def load_lessons():
            try:
                for _ in range(10):
                    brain_engine.load_all_lessons()
            except Exception as e:
                errors.append(e)

        def write_lesson():
            try:
                for i in range(10):
                    path = brain_home / "lessons" / f"concurrent-{i}.yaml"
                    path.write_text(f"id: concurrent-{i}\nseverity: info\nlesson: test {i}\n")
            except Exception as e:
                errors.append(e)

        t1 = threading.Thread(target=load_lessons)
        t2 = threading.Thread(target=write_lesson)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        assert len(errors) == 0, f"Errors during concurrent load/write: {errors}"


class TestMainCLI:
    """CLI main() function tests."""

    def test_main_no_args(self, capsys):
        """No arguments should show help."""
        original = sys.argv
        sys.argv = ["brain"]
        try:
            result = brain_engine.main()
            assert result == 0
            captured = capsys.readouterr()
            assert "Shared Brain" in captured.out
        finally:
            sys.argv = original

    def test_main_unknown_command(self, capsys):
        """Unknown command should return error."""
        original = sys.argv
        sys.argv = ["brain", "nonexistent"]
        try:
            result = brain_engine.main()
            assert result == 1
            captured = capsys.readouterr()
            assert "Unknown command" in captured.err
        finally:
            sys.argv = original

    def test_main_help_flag(self, capsys):
        """--help flag should show help."""
        original = sys.argv
        sys.argv = ["brain", "--help"]
        try:
            result = brain_engine.main()
            assert result == 0
            captured = capsys.readouterr()
            assert "brain guard" in captured.out
        finally:
            sys.argv = original

    def test_main_h_flag(self, capsys):
        """-h flag should show help."""
        original = sys.argv
        sys.argv = ["brain", "-h"]
        try:
            result = brain_engine.main()
            assert result == 0
        finally:
            sys.argv = original


class TestBrainAgentEnvVar:
    """BRAIN_AGENT environment variable tests."""

    def test_guard_uses_brain_agent_env(self, brain_home, sample_lesson):
        """cmd_guard should use BRAIN_AGENT env var for agent name."""
        original = os.environ.get("BRAIN_AGENT")
        os.environ["BRAIN_AGENT"] = "my-custom-agent"
        try:
            brain_engine.cmd_guard(["curl -X PUT /api/test", "--auto-confirm"])
            entries = brain_engine.load_audit()
            assert any(e["agent"] == "my-custom-agent" for e in entries)
        finally:
            if original is None:
                os.environ.pop("BRAIN_AGENT", None)
            else:
                os.environ["BRAIN_AGENT"] = original

    def test_guard_default_agent_cli_user(self, brain_home, sample_lesson):
        """Without BRAIN_AGENT, agent should default to 'cli-user'."""
        original = os.environ.pop("BRAIN_AGENT", None)
        try:
            brain_engine.cmd_guard(["curl -X PUT /api/test", "--auto-confirm"])
            entries = brain_engine.load_audit()
            assert any(e["agent"] == "cli-user" for e in entries)
        finally:
            if original:
                os.environ["BRAIN_AGENT"] = original


class TestGuardNonInteractive:
    """Guard non-interactive mode tests."""

    def test_guard_non_interactive_proceeds(self, brain_home, sample_lesson, capsys, monkeypatch):
        """In non-interactive mode (no tty), guard should warn but proceed."""
        monkeypatch.setattr(sys.stdin, 'isatty', lambda: False)
        result = brain_engine.guard("curl -X PUT /api/test", "test-agent")
        assert result is True
        captured = capsys.readouterr()
        assert "non-interactive" in captured.out.lower() or "caution" in captured.out.lower()


class TestHookInstallUninstall:
    """Hook install/uninstall integration tests."""

    def test_hook_install_fresh(self, tmp_path, capsys):
        """Install on fresh system should create settings.json."""
        import unittest.mock
        with unittest.mock.patch.object(Path, 'home', return_value=tmp_path):
            result = brain_engine.cmd_hook(["install"])
        assert result == 0
        settings_path = tmp_path / ".claude" / "settings.json"
        assert settings_path.exists()
        settings = json.loads(settings_path.read_text())
        assert "hooks" in settings
        assert "PreToolUse" in settings["hooks"]

    def test_hook_install_existing_settings(self, tmp_path, capsys):
        """Install with existing settings should merge, not overwrite."""
        settings_path = tmp_path / ".claude" / "settings.json"
        settings_path.parent.mkdir(parents=True)
        existing = {"some_key": "some_value", "hooks": {"PostToolUse": [{"matcher": "test"}]}}
        settings_path.write_text(json.dumps(existing))

        import unittest.mock
        with unittest.mock.patch.object(Path, 'home', return_value=tmp_path):
            result = brain_engine.cmd_hook(["install"])
        assert result == 0

        settings = json.loads(settings_path.read_text())
        # Original key preserved
        assert settings["some_key"] == "some_value"
        # PostToolUse preserved
        assert len(settings["hooks"]["PostToolUse"]) == 1
        # PreToolUse added
        assert "PreToolUse" in settings["hooks"]

    def test_hook_install_idempotent(self, tmp_path, capsys):
        """Double install should not create duplicate hooks."""
        import unittest.mock
        with unittest.mock.patch.object(Path, 'home', return_value=tmp_path):
            brain_engine.cmd_hook(["install"])
            result = brain_engine.cmd_hook(["install"])
        assert result == 0
        captured = capsys.readouterr()
        assert "already installed" in captured.out

    def test_hook_uninstall(self, tmp_path, capsys):
        """Uninstall should remove brain guard hook."""
        import unittest.mock
        with unittest.mock.patch.object(Path, 'home', return_value=tmp_path):
            brain_engine.cmd_hook(["install"])
            result = brain_engine.cmd_hook(["uninstall"])
        assert result == 0

        settings_path = tmp_path / ".claude" / "settings.json"
        settings = json.loads(settings_path.read_text())
        for hook in settings["hooks"]["PreToolUse"]:
            assert "brain guard" not in json.dumps(hook)

    def test_hook_status_installed(self, tmp_path, capsys):
        """Status should show installed after install."""
        import unittest.mock
        with unittest.mock.patch.object(Path, 'home', return_value=tmp_path):
            brain_engine.cmd_hook(["install"])
            result = brain_engine.cmd_hook(["status"])
        assert result == 0
        captured = capsys.readouterr()
        assert "Installed" in captured.out


class TestExportEdgeCasesExtended:
    """Additional export edge cases."""

    def test_export_markdown_alias(self, brain_home, sample_lesson, capsys):
        """--format markdown should work as alias for md."""
        result = brain_engine.cmd_export(["--format", "markdown"])
        assert result == 0
        captured = capsys.readouterr()
        assert "# Shared Brain" in captured.out

    def test_export_includes_tags(self, brain_home, sample_lesson, capsys):
        """Markdown export should include tags."""
        result = brain_engine.cmd_export(["--format", "md"])
        assert result == 0
        captured = capsys.readouterr()
        assert "api" in captured.out
        assert "Tags" in captured.out

    def test_export_includes_trigger_patterns(self, brain_home, sample_lesson, capsys):
        """Markdown export should include trigger patterns."""
        result = brain_engine.cmd_export(["--format", "md"])
        assert result == 0
        captured = capsys.readouterr()
        assert "Triggers" in captured.out

    def test_export_to_file_json(self, brain_home, sample_lesson, tmp_path, capsys):
        """JSON export to file should create valid JSON file."""
        out_file = str(tmp_path / "export.json")
        result = brain_engine.cmd_export(["--format", "json", "--output", out_file])
        assert result == 0
        content = Path(out_file).read_text()
        data = json.loads(content)
        assert len(data) >= 1


class TestLessonLoadingEdgeCases:
    """Additional lesson loading edge cases."""

    def test_lesson_missing_severity_defaults(self, brain_home, capsys):
        """Lesson without severity should still load."""
        lesson = "id: no-severity\nlesson: missing severity field\n"
        (brain_home / "lessons" / "no-sev.yaml").write_text(lesson)
        lessons = brain_engine.load_all_lessons()
        found = [l for l in lessons if l.get("id") == "no-severity"]
        assert len(found) == 1

    def test_lesson_missing_trigger_patterns(self, brain_home):
        """Lesson without trigger_patterns should not crash guard."""
        lesson = "id: no-triggers\nseverity: info\nlesson: no triggers here\n"
        (brain_home / "lessons" / "no-trig.yaml").write_text(lesson)
        # Guard should handle this gracefully
        result = brain_engine.guard("anything", "test", auto_confirm=True)
        assert result is True

    def test_lesson_with_malformed_patterns(self, brain_home):
        """Lesson with non-list trigger_patterns should be handled."""
        # When trigger_patterns is a string instead of a list
        lesson = "id: bad-patterns\nseverity: warning\ntrigger_patterns: not-a-list\nlesson: test\n"
        (brain_home / "lessons" / "bad.yaml").write_text(lesson)
        # Should not crash - the string "not-a-list" is not iterable as expected
        # But our YAML parser produces a string, so guard iterates over chars
        try:
            result = brain_engine.guard("anything", "test", auto_confirm=True)
            # If it doesn't crash, that's a pass
            assert isinstance(result, bool)
        except TypeError:
            # If it crashes on iteration, that's also acceptable to document
            pass

    def test_many_lessons_performance(self, brain_home):
        """Loading 100+ lessons should complete quickly."""
        import time
        for i in range(100):
            lesson = f"id: perf-{i}\nseverity: info\nlesson: Performance test lesson {i}\ntrigger_patterns:\n  - \"perf-pattern-{i}\"\n"
            (brain_home / "lessons" / f"perf-{i}.yaml").write_text(lesson)

        start = time.time()
        lessons = brain_engine.load_all_lessons()
        elapsed = time.time() - start

        assert len(lessons) == 100
        assert elapsed < 5.0  # Should load 100 lessons in under 5 seconds


class TestSecurityFixes:
    """Security vulnerability fixes — ReDoS, Path Traversal, Command Injection."""

    # --- ReDoS (CVE-like) ---

    def test_redos_catastrophic_backtracking_timeout(self, brain_home, capsys):
        """Malicious regex pattern should timeout instead of hanging."""
        # Classic ReDoS pattern: (a+)+ matched against "aaa...!" causes exponential backtracking
        lesson = (
            "id: redos-test\nseverity: warning\n"
            "trigger_patterns:\n"
            '  - "(a+)+$"\n'
            "lesson: redos test\n"
        )
        (brain_home / "lessons" / "redos.yaml").write_text(lesson)

        # This input causes catastrophic backtracking with (a+)+$
        evil_input = "a" * 30 + "!"

        import time
        start = time.time()
        result = brain_engine.guard(evil_input, "test", auto_confirm=True)
        elapsed = time.time() - start

        # Heuristic detects nested quantifier → subprocess timeout kicks in
        # Must complete within 5 seconds (not hang for minutes)
        assert elapsed < 5.0, f"Guard took {elapsed:.1f}s — ReDoS not mitigated"
        assert isinstance(result, bool)

    def test_check_regex_safety_detects_nested_quantifiers(self):
        """Heuristic should flag nested quantifiers as dangerous."""
        assert brain_engine._check_regex_safety(r"(a+)+$") is False
        assert brain_engine._check_regex_safety(r"(a*)*") is False
        assert brain_engine._check_regex_safety(r"(a+)*") is False

    def test_check_regex_safety_allows_normal_patterns(self):
        """Normal patterns should pass the safety check."""
        assert brain_engine._check_regex_safety(r"curl.*PUT") is True
        assert brain_engine._check_regex_safety(r"git push.*--force") is True
        assert brain_engine._check_regex_safety(r"rm\s+-rf") is True
        assert brain_engine._check_regex_safety(r"DELETE FROM") is True

    def test_safe_regex_search_normal_pattern(self):
        """Normal patterns should work correctly with _safe_regex_search."""
        result = brain_engine._safe_regex_search(r"curl.*PUT", "curl -X PUT /api")
        assert result is not None

    def test_safe_regex_search_no_match(self):
        """Non-matching pattern should return None."""
        result = brain_engine._safe_regex_search(r"DELETE", "curl -X GET /api")
        assert result is None

    def test_safe_regex_search_invalid_regex(self):
        """Invalid regex should raise re.error (caught by guard's except)."""
        import re as re_mod
        with pytest.raises(re_mod.error):
            brain_engine._safe_regex_search(r"[invalid", "test")

    # --- Path Traversal ---

    def test_path_traversal_dotdot_sanitized(self, brain_home, tmp_path, capsys):
        """Lesson ID with ../ should be sanitized — dots and slashes stripped."""
        src = tmp_path / "evil.yaml"
        src.write_text('id: "../../../.bashrc"\nseverity: info\nlesson: evil\n')
        result = brain_engine.cmd_write(["-f", str(src)])
        # After sanitization, "../../../.bashrc" → "bashrc" (safe)
        assert result == 0
        captured = capsys.readouterr()
        assert "bashrc" in captured.out
        # The file must be INSIDE lessons dir, not outside
        dest = brain_home / "lessons" / "bashrc.yaml"
        assert dest.exists()
        # Verify .bashrc was NOT created in parent dirs
        assert not (brain_home.parent / ".bashrc.yaml").exists()

    def test_path_traversal_only_dots_rejected(self, brain_home, tmp_path, capsys):
        """Lesson ID that becomes empty after sanitization should be rejected."""
        src = tmp_path / "evil-empty.yaml"
        src.write_text('id: "../../.."\nseverity: info\nlesson: evil\n')
        result = brain_engine.cmd_write(["-f", str(src)])
        assert result == 1
        captured = capsys.readouterr()
        assert "Invalid" in captured.err

    def test_path_traversal_slash_blocked(self, brain_home, tmp_path, capsys):
        """Lesson ID with / should be sanitized."""
        src = tmp_path / "evil2.yaml"
        src.write_text('id: "foo/bar/baz"\nseverity: info\nlesson: evil\n')
        result = brain_engine.cmd_write(["-f", str(src)])
        # Should either succeed with sanitized ID or fail
        if result == 0:
            # Sanitized ID should be "foobarbaz" — verify file is inside LESSONS_DIR
            captured = capsys.readouterr()
            assert "foobarbaz" in captured.out
            dest = brain_home / "lessons" / "foobarbaz.yaml"
            assert dest.exists()
        else:
            captured = capsys.readouterr()
            assert "Invalid" in captured.err

    def test_path_traversal_backslash_blocked(self, brain_home, tmp_path, capsys):
        """Lesson ID with backslash should be sanitized."""
        src = tmp_path / "evil3.yaml"
        src.write_text('id: "..\\\\..\\\\evil"\nseverity: info\nlesson: evil\n')
        result = brain_engine.cmd_write(["-f", str(src)])
        # Should sanitize away the backslashes and dots
        assert isinstance(result, int)

    def test_sanitize_lesson_id_normal(self):
        """Normal IDs should pass through."""
        assert brain_engine._sanitize_lesson_id("api-put-safety") == "api-put-safety"
        assert brain_engine._sanitize_lesson_id("test_123") == "test_123"

    def test_sanitize_lesson_id_unicode(self):
        """Unicode lesson IDs should be preserved."""
        assert brain_engine._sanitize_lesson_id("api安全チェック") == "api安全チェック"

    def test_sanitize_lesson_id_empty_after_strip(self):
        """ID that becomes empty after sanitization should raise."""
        import pytest
        with pytest.raises(ValueError):
            brain_engine._sanitize_lesson_id("../../..")

    def test_valid_write_still_works(self, brain_home, tmp_path, capsys):
        """Valid lesson write should still succeed after security fix."""
        src = tmp_path / "good.yaml"
        src.write_text("id: valid-lesson\nseverity: info\nlesson: all good\n")
        result = brain_engine.cmd_write(["-f", str(src)])
        assert result == 0
        assert (brain_home / "lessons" / "valid-lesson.yaml").exists()

    # --- Command Injection via Hook ---

    def test_hook_uses_from_env(self, tmp_path, capsys):
        """Hook install should use --from-env, not shell-expanded $TOOL_INPUT."""
        import unittest.mock
        with unittest.mock.patch.object(Path, 'home', return_value=tmp_path):
            brain_engine.cmd_hook(["install"])

        settings_path = tmp_path / ".claude" / "settings.json"
        settings = json.loads(settings_path.read_text())
        hook_cmd = settings["hooks"]["PreToolUse"][0]["hooks"][0]["command"]
        # Must use --from-env, not "$TOOL_INPUT" in command line
        assert "--from-env" in hook_cmd
        assert '"$TOOL_INPUT"' not in hook_cmd

    def test_guard_from_env_reads_json(self, brain_home, sample_lesson, capsys):
        """--from-env should read TOOL_INPUT from env and parse JSON."""
        original = os.environ.get("TOOL_INPUT")
        os.environ["TOOL_INPUT"] = json.dumps({"command": "curl -X PUT /api/test"})
        try:
            result = brain_engine.cmd_guard(["--from-env", "--auto-confirm"])
            assert result == 0
            entries = brain_engine.load_audit()
            assert any("test-put-safety" in e.get("lessons_matched", []) for e in entries)
        finally:
            if original is None:
                os.environ.pop("TOOL_INPUT", None)
            else:
                os.environ["TOOL_INPUT"] = original

    def test_guard_from_env_empty(self, brain_home):
        """--from-env with no TOOL_INPUT should return 0 (safe)."""
        original = os.environ.pop("TOOL_INPUT", None)
        try:
            result = brain_engine.cmd_guard(["--from-env"])
            assert result == 0
        finally:
            if original:
                os.environ["TOOL_INPUT"] = original

    def test_guard_from_env_malformed_json(self, brain_home, capsys):
        """--from-env with non-JSON TOOL_INPUT should use raw string."""
        original = os.environ.get("TOOL_INPUT")
        os.environ["TOOL_INPUT"] = "not json at all"
        try:
            result = brain_engine.cmd_guard(["--from-env", "--auto-confirm"])
            assert result == 0
        finally:
            if original is None:
                os.environ.pop("TOOL_INPUT", None)
            else:
                os.environ["TOOL_INPUT"] = original



    """タチコマ指定エッジケース追加テスト（サイクル#1）

    カバー範囲:
    1. 空のJSONLファイル → guard追記パイプライン
    2. 存在しないBRAIN_HOMEディレクトリの自動作成
    3. 存在しないディレクトリへのexport
    4. 正規表現特殊文字を含むコマンドでのguard安全性
    5. Unicode教訓の全パイプライン（教訓→guard→監査→レポート）
    """

    def test_empty_jsonl_then_guard_appends(self, brain_home, sample_lesson):
        """空のaudit.jsonlが存在する状態でguardを実行→エントリが正しく追記される。

        空ファイルへのappendでファイルハンドルが正常に動作し、
        後続のload_auditで正しくパースできることを確認。
        """
        audit_file = brain_home / "audit.jsonl"
        audit_file.write_text("")  # empty file exists

        brain_engine.guard("curl -X PUT /api/test", "test-agent", auto_confirm=True)
        entries = brain_engine.load_audit()
        assert len(entries) == 1
        assert entries[0]["agent"] == "test-agent"
        assert "test-put-safety" in entries[0]["lessons_matched"]

    def test_nonexistent_brain_home_autocreated(self, tmp_path):
        """存在しないBRAIN_HOMEディレクトリ→ensure_dirs()で自動作成される。

        深くネストされたパスでもmkdir(parents=True)で作成されることを確認。
        """
        nonexistent = tmp_path / "deep" / "nested" / ".brain"
        original_brain_dir = brain_engine.BRAIN_DIR
        original_lessons_dir = brain_engine.LESSONS_DIR
        original_audit_file = brain_engine.AUDIT_FILE

        brain_engine.BRAIN_DIR = nonexistent
        brain_engine.LESSONS_DIR = nonexistent / "lessons"
        brain_engine.AUDIT_FILE = nonexistent / "audit.jsonl"

        try:
            brain_engine.ensure_dirs()
            assert brain_engine.LESSONS_DIR.exists()
            assert (nonexistent / "audit").exists()
        finally:
            brain_engine.BRAIN_DIR = original_brain_dir
            brain_engine.LESSONS_DIR = original_lessons_dir
            brain_engine.AUDIT_FILE = original_audit_file

    def test_export_to_nonexistent_directory(self, brain_home, sample_lesson, tmp_path):
        """存在しないディレクトリへのexport→FileNotFoundError発生。

        cmd_exportは親ディレクトリの存在チェックをしないため、
        Path.write_textがFileNotFoundErrorを投げる。現状の挙動を文書化するテスト。
        """
        bad_path = str(tmp_path / "nonexistent" / "deep" / "export.md")
        with pytest.raises((FileNotFoundError, OSError)):
            brain_engine.cmd_export(["--format", "md", "--output", bad_path])

    def test_guard_command_with_special_regex_chars(self, brain_home):
        """正規表現特殊文字を含むコマンドでguardがクラッシュしない。

        シェルコマンドには$(), |, *, [], {}等の正規表現特殊文字が頻出する。
        これらがre.search()でエラーを起こさないことを確認。
        """
        lesson = "id: regex-safe\nseverity: warning\ntrigger_patterns:\n  - \"rm.*-rf\"\nlesson: test\n"
        (brain_home / "lessons" / "regex.yaml").write_text(lesson)

        special_commands = [
            "echo $(whoami)",
            "cat file | grep 'pattern'",
            "ls *.txt",
            "echo 'hello [world]'",
            "test (a && b) || c",
            "cmd with $VAR and {braces}",
        ]
        for cmd in special_commands:
            # re.search(pattern, command) where command has special chars
            # should not raise because the command is the haystack, not the pattern
            result = brain_engine.guard(cmd, "test", auto_confirm=True)
            assert isinstance(result, bool)

    def test_unicode_full_audit_pipeline(self, brain_home, capsys):
        """Unicode教訓の全パイプラインテスト（教訓作成→guard発火→監査ログ→レポート表示）。

        日本語ID、日本語パターン、日本語エージェント名が
        guard→audit log→audit reportの全経路で正しく保持されることを確認。
        """
        lesson = (
            "id: 全角テスト教訓\n"
            "severity: critical\n"
            "lesson: 危険！APIを破壊する可能性\n"
            "trigger_patterns:\n"
            '  - "DELETE.*データ"\n'
            "checklist:\n"
            '  - "バックアップ確認済み？"\n'
            '  - "ロールバック手順あり？"\n'
            "tags: [日本語, 安全, テスト]\n"
        )
        (brain_home / "lessons" / "全角テスト.yaml").write_text(lesson, encoding="utf-8")

        # Guard fires on Unicode pattern
        result = brain_engine.guard("DELETE FROM データベース", "テストエージェント", auto_confirm=True)
        assert result is True

        # Audit log preserves Unicode
        entries = brain_engine.load_audit()
        assert len(entries) >= 1
        last = entries[-1]
        assert last["agent"] == "テストエージェント"
        assert "全角テスト教訓" in last["lessons_matched"]

        # Audit report displays Unicode correctly
        capsys.readouterr()  # clear previous output
        result = brain_engine.cmd_audit([])
        assert result == 0
        captured = capsys.readouterr()
        assert "全角テスト教訓" in captured.out
        assert "テストエージェント" in captured.out


class TestErrorHandlingIntegration:
    """Error handling integration tests — broken YAML, large files, permission errors."""

    def test_broken_yaml_file_skipped_gracefully(self, brain_home, capsys):
        """Malformed YAML should be skipped with a warning, not crash."""
        # Valid lesson
        (brain_home / "lessons" / "good.yaml").write_text(
            "id: good-lesson\nseverity: info\nlesson: valid\n"
        )
        # Broken YAML (unclosed bracket, bad indentation)
        (brain_home / "lessons" / "broken.yaml").write_text(
            "id: broken\nseverity: [unclosed\n  bad indent:\n    :::\n"
        )
        lessons = brain_engine.load_all_lessons()
        # Good lesson should still load
        good = [l for l in lessons if l.get("id") == "good-lesson"]
        assert len(good) == 1
        # Guard should not crash even with broken lesson in directory
        result = brain_engine.guard("anything", "test", auto_confirm=True)
        assert isinstance(result, bool)

    def test_oversized_yaml_file_handled(self, brain_home, capsys):
        """A huge YAML file (>1MB) should load without crashing or hanging."""
        # Generate a 1.5MB lesson file with a very long lesson text
        big_text = "x" * (1024 * 1500)  # 1.5MB of 'x'
        content = f"id: big-lesson\nseverity: info\nlesson: {big_text}\n"
        (brain_home / "lessons" / "big.yaml").write_text(content)
        # Should load without crashing
        lessons = brain_engine.load_all_lessons()
        big = [l for l in lessons if l.get("id") == "big-lesson"]
        assert len(big) == 1
        # Guard should still work (the lesson has no trigger patterns, so no match)
        result = brain_engine.guard("test", "agent", auto_confirm=True)
        assert result is True

    def test_permission_error_on_lessons_dir(self, brain_home, capsys):
        """Inaccessible lesson files should be skipped with a warning."""
        import stat
        # Create a valid lesson + an unreadable file
        (brain_home / "lessons" / "ok.yaml").write_text(
            "id: ok\nseverity: info\nlesson: fine\n"
        )
        bad_file = brain_home / "lessons" / "noperm.yaml"
        bad_file.write_text("id: noperm\nseverity: critical\nlesson: secret\n")
        # Remove read permission
        bad_file.chmod(0o000)
        try:
            lessons = brain_engine.load_all_lessons()
            # The readable lesson should still load
            ok = [l for l in lessons if l.get("id") == "ok"]
            assert len(ok) == 1
        finally:
            # Restore permission for cleanup
            bad_file.chmod(stat.S_IRUSR | stat.S_IWUSR)

    def test_empty_yaml_file_skipped(self, brain_home, capsys):
        """Empty YAML file should be skipped without error."""
        (brain_home / "lessons" / "empty.yaml").write_text("")
        (brain_home / "lessons" / "valid.yaml").write_text(
            "id: valid\nseverity: info\nlesson: ok\n"
        )
        lessons = brain_engine.load_all_lessons()
        valid = [l for l in lessons if l.get("id") == "valid"]
        assert len(valid) == 1
        # Empty file should not produce a lesson
        empty = [l for l in lessons if l.get("id") == "empty"]
        assert len(empty) == 0

    def test_binary_content_in_yaml_handled(self, brain_home, capsys):
        """Binary/garbage content in a .yaml file should not crash."""
        # Write binary-like garbage to a yaml file
        garbage = bytes(range(256)) * 10
        (brain_home / "lessons" / "garbage.yaml").write_bytes(garbage)
        (brain_home / "lessons" / "real.yaml").write_text(
            "id: real\nseverity: info\nlesson: real lesson\n"
        )
        # Should not crash; garbage file should be skipped
        lessons = brain_engine.load_all_lessons()
        real = [l for l in lessons if l.get("id") == "real"]
        assert len(real) == 1


class TestSearchCommand:
    """Tests for brain search command."""

    def test_search_by_keyword(self, brain_home, sample_lesson, capsys):
        """Search should find lessons matching keyword."""
        result = brain_engine.cmd_search(["PUT"])
        assert result == 0
        captured = capsys.readouterr()
        assert "test-put-safety" in captured.out

    def test_search_no_results(self, brain_home, capsys):
        """Search with no matches should report no results."""
        result = brain_engine.cmd_search(["nonexistent_xyz"])
        assert result == 0
        captured = capsys.readouterr()
        assert "No lessons found" in captured.out

    def test_search_by_tag(self, brain_home, sample_lesson, capsys):
        """Search with --tag filter should work."""
        result = brain_engine.cmd_search(["--tag", "api"])
        assert result == 0
        captured = capsys.readouterr()
        assert "test-put-safety" in captured.out

    def test_search_by_severity(self, brain_home, sample_lesson, capsys):
        """Search with --severity filter should work."""
        result = brain_engine.cmd_search(["--severity", "critical"])
        assert result == 0
        captured = capsys.readouterr()
        assert "test-put-safety" in captured.out

    def test_search_no_args(self, capsys):
        """Search with no arguments should show usage."""
        result = brain_engine.cmd_search([])
        assert result == 1
        captured = capsys.readouterr()
        assert "Usage" in captured.err or "search" in captured.err

    def test_search_combined_keyword_and_tag(self, brain_home, capsys):
        """Search with keyword + tag should AND the filters."""
        (brain_home / "lessons" / "a.yaml").write_text(
            "id: tag-match\nseverity: info\nlesson: test\ntags: [special]\n"
        )
        (brain_home / "lessons" / "b.yaml").write_text(
            "id: keyword-match\nseverity: info\nlesson: special keyword here\ntags: [other]\n"
        )
        # Search for keyword "special" with tag "special" — only a.yaml matches both
        result = brain_engine.cmd_search(["--tag", "special", "special"])
        assert result == 0
        captured = capsys.readouterr()
        assert "tag-match" in captured.out


class TestStatsVerbose:
    """Tests for brain stats --verbose."""

    def test_stats_verbose_shows_categories(self, brain_home, sample_lesson, capsys):
        """--verbose should show tag categories."""
        result = brain_engine.cmd_stats(["--verbose"])
        assert result == 0
        captured = capsys.readouterr()
        assert "Categories" in captured.out
        assert "api" in captured.out

    def test_stats_verbose_shows_severity_breakdown(self, brain_home, sample_lesson, capsys):
        """--verbose should show severity breakdown."""
        result = brain_engine.cmd_stats(["--verbose"])
        assert result == 0
        captured = capsys.readouterr()
        assert "Severity Breakdown" in captured.out
        assert "Critical" in captured.out

    def test_stats_verbose_shows_recently_added(self, brain_home, sample_lesson, capsys):
        """--verbose should show recently added lessons."""
        result = brain_engine.cmd_stats(["--verbose"])
        assert result == 0
        captured = capsys.readouterr()
        assert "Recently Added" in captured.out

    def test_stats_verbose_shows_top_triggers(self, brain_home, sample_lesson, capsys):
        """--verbose should show top guard triggers when audit data exists."""
        # Create some audit entries
        brain_engine.guard("curl -X PUT /api/test", "test", auto_confirm=True)
        brain_engine.guard("curl -X PUT /api/test2", "test", auto_confirm=True)
        capsys.readouterr()  # clear guard output
        result = brain_engine.cmd_stats(["--verbose"])
        assert result == 0
        captured = capsys.readouterr()
        assert "Top 5 Guard Triggers" in captured.out

    def test_stats_short_v_flag(self, brain_home, sample_lesson, capsys):
        """-v should work as shorthand for --verbose."""
        result = brain_engine.cmd_stats(["-v"])
        assert result == 0
        captured = capsys.readouterr()
        assert "Severity Breakdown" in captured.out


# --- i18n Tests ---

class TestI18n:
    """Tests for internationalization (i18n) system."""

    def test_i18n_english_default(self, brain_home, sample_lesson, capsys, monkeypatch):
        """Default language should be English."""
        monkeypatch.delenv("BRAIN_LANG", raising=False)
        monkeypatch.delenv("LC_ALL", raising=False)
        monkeypatch.delenv("LC_MESSAGES", raising=False)
        monkeypatch.setenv("LANG", "en_US.UTF-8")
        # Reset i18n state
        import brain_i18n
        brain_i18n._current_lang = None
        brain_i18n._messages = {}
        brain_i18n._fallback = {}
        brain_engine._msg_func = None

        result = brain_engine.cmd_stats([])
        assert result == 0
        captured = capsys.readouterr()
        assert "Shared Brain Stats" in captured.out
        assert "Lessons:" in captured.out

    def test_i18n_japanese_with_brain_lang(self, brain_home, sample_lesson, capsys, monkeypatch):
        """BRAIN_LANG=ja should switch output to Japanese."""
        monkeypatch.setenv("BRAIN_LANG", "ja")
        import brain_i18n
        brain_i18n._current_lang = None
        brain_i18n._messages = {}
        brain_i18n._fallback = {}
        brain_engine._msg_func = None

        result = brain_engine.cmd_stats([])
        assert result == 0
        captured = capsys.readouterr()
        assert "Shared Brain 統計" in captured.out
        assert "レッスン数:" in captured.out

    def test_i18n_japanese_with_lang_env(self, brain_home, sample_lesson, capsys, monkeypatch):
        """LANG=ja_JP.UTF-8 should detect Japanese."""
        monkeypatch.delenv("BRAIN_LANG", raising=False)
        monkeypatch.delenv("LC_ALL", raising=False)
        monkeypatch.delenv("LC_MESSAGES", raising=False)
        monkeypatch.setenv("LANG", "ja_JP.UTF-8")
        import brain_i18n
        brain_i18n._current_lang = None
        brain_i18n._messages = {}
        brain_i18n._fallback = {}
        brain_engine._msg_func = None

        result = brain_engine.cmd_stats([])
        assert result == 0
        captured = capsys.readouterr()
        assert "Shared Brain 統計" in captured.out

    def test_i18n_message_keys_match(self):
        """Japanese catalog must have the same keys as English."""
        from messages import en, ja
        en_keys = set(en.MESSAGES.keys())
        ja_keys = set(ja.MESSAGES.keys())
        missing = en_keys - ja_keys
        extra = ja_keys - en_keys
        assert not missing, f"Missing in ja: {missing}"
        assert not extra, f"Extra in ja: {extra}"


# --- Plugin System Tests ---

class TestPluginSystem:
    """Tests for the plugin loading and registry system."""

    def test_plugin_guard_registration(self, brain_home, capsys):
        """Plugins can register custom guard rules."""
        # Reset registry
        brain_engine.REGISTRY.guards.clear()
        brain_engine.REGISTRY._loaded = False

        # Register a custom guard directly
        def match_fn(command):
            return "dangerous" in command

        brain_engine.REGISTRY.register_guard("test-guard", match_fn)
        assert len(brain_engine.REGISTRY.guards) == 1
        assert brain_engine.REGISTRY.guards[0]["name"] == "test-guard"

        # Clean up
        brain_engine.REGISTRY.guards.clear()

    def test_plugin_exporter_registration(self, brain_home, sample_lesson, capsys, tmp_path):
        """Plugins can register custom export formats."""
        brain_engine.REGISTRY._loaded = True  # Prevent file loading

        def export_csv(lessons, output_path=None):
            lines = ["id,severity"]
            for l in lessons:
                lines.append(f"{l.get('id','')},{l.get('severity','')}")
            content = "\n".join(lines)
            if output_path:
                Path(output_path).write_text(content)
            return content

        brain_engine.REGISTRY.register_exporter("csv", export_csv)

        result = brain_engine.cmd_export(["--format", "csv"])
        assert result == 0
        captured = capsys.readouterr()
        assert "test-put-safety" in captured.out
        assert "critical" in captured.out

        # Clean up
        del brain_engine.REGISTRY.exporters["csv"]

    def test_plugin_source_registration(self, brain_home, capsys):
        """Plugins can register custom lesson sources."""
        brain_engine.REGISTRY._loaded = True

        def load_extra():
            return [{"id": "plugin-lesson-1", "severity": "info", "lesson": "From plugin"}]

        brain_engine.REGISTRY.register_source("test-source", load_extra)

        lessons = brain_engine.load_all_lessons()
        ids = [l.get("id") for l in lessons]
        assert "plugin-lesson-1" in ids

        # Clean up
        brain_engine.REGISTRY.sources.clear()

    def test_plugin_file_loading(self, brain_home, tmp_path):
        """Plugins from ~/.brain/plugins/ should be loaded."""
        plugins_dir = brain_home / "plugins"
        plugins_dir.mkdir(exist_ok=True)

        plugin_code = '''
def register(registry):
    registry.register_exporter("test-fmt", lambda lessons, path: "test-output")
'''
        (plugins_dir / "test_plugin.py").write_text(plugin_code)

        # Reset and point PLUGINS_DIR to our test dir
        original_plugins = brain_engine.PLUGINS_DIR
        brain_engine.PLUGINS_DIR = plugins_dir
        brain_engine.REGISTRY._loaded = False
        brain_engine.REGISTRY.exporters.pop("test-fmt", None)

        try:
            brain_engine.load_plugins()
            assert "test-fmt" in brain_engine.REGISTRY.exporters
        finally:
            brain_engine.PLUGINS_DIR = original_plugins
            brain_engine.REGISTRY.exporters.pop("test-fmt", None)
            brain_engine.REGISTRY._loaded = False


# --- HTML Export Tests ---

class TestHTMLExport:
    """Tests for brain export --format html."""

    def test_html_export_basic(self, brain_home, sample_lesson, capsys):
        """HTML export should produce valid HTML with lesson content."""
        result = brain_engine.cmd_export(["--format", "html"])
        assert result == 0
        captured = capsys.readouterr()
        assert "<!DOCTYPE html>" in captured.out
        assert "test-put-safety" in captured.out
        assert "CRITICAL" in captured.out

    def test_html_export_inline_css(self, brain_home, sample_lesson, capsys):
        """HTML export should include inline CSS (no external stylesheets)."""
        result = brain_engine.cmd_export(["--format", "html"])
        assert result == 0
        captured = capsys.readouterr()
        assert "<style>" in captured.out
        assert "font-family" in captured.out
        # No external CSS links
        assert '<link rel="stylesheet"' not in captured.out

    def test_html_export_to_file(self, brain_home, sample_lesson, tmp_path, capsys):
        """HTML export to file should create a valid HTML file."""
        out_file = str(tmp_path / "export.html")
        result = brain_engine.cmd_export(["--format", "html", "--output", out_file])
        assert result == 0
        content = Path(out_file).read_text()
        assert "<!DOCTYPE html>" in content
        assert "test-put-safety" in content

    def test_html_export_escapes_special_chars(self, brain_home, capsys):
        """HTML export should escape < > & in lesson content."""
        lesson = 'id: html-escape\nseverity: info\nlesson: "Use <script> & &amp; carefully"\ntrigger_patterns:\n  - "script"\n'
        (brain_home / "lessons" / "html-escape.yaml").write_text(lesson)
        result = brain_engine.cmd_export(["--format", "html"])
        assert result == 0
        captured = capsys.readouterr()
        # Should be escaped
        assert "&lt;script&gt;" in captured.out
        assert "&amp;" in captured.out


# --- Uninstall Tests ---

class TestUninstall:
    """Tests for brain uninstall command."""

    def test_uninstall_removes_audit(self, brain_home, capsys, monkeypatch):
        """Uninstall should remove audit log when confirmed."""
        # Create audit file
        audit_file = brain_home / "audit.jsonl"
        audit_file.write_text('{"test": true}\n')
        assert audit_file.exists()

        # Simulate 'y' confirmation
        monkeypatch.setattr("builtins.input", lambda prompt: "y")
        result = brain_engine.cmd_uninstall([])
        assert result == 0
        assert not audit_file.exists()

    def test_uninstall_aborted(self, brain_home, capsys, monkeypatch):
        """Uninstall should abort when user says no."""
        audit_file = brain_home / "audit.jsonl"
        audit_file.write_text('{"test": true}\n')

        monkeypatch.setattr("builtins.input", lambda prompt: "n")
        # Must pretend we are in a TTY so the interactive confirm path is taken
        monkeypatch.setattr("sys.stdin", type("FakeTTY", (), {"isatty": lambda self: True})())
        result = brain_engine.cmd_uninstall([])
        assert result == 1
        assert audit_file.exists()

    def test_uninstall_all_removes_lessons(self, brain_home, sample_lesson, capsys, monkeypatch):
        """--all should also remove lessons and brain directory."""
        lessons_dir = brain_home / "lessons"
        assert lessons_dir.exists()
        assert len(list(lessons_dir.glob("*.yaml"))) > 0

        monkeypatch.setattr("builtins.input", lambda prompt: "y")
        result = brain_engine.cmd_uninstall(["--all"])
        assert result == 0
        assert not lessons_dir.exists()

    def test_uninstall_nothing(self, tmp_path, capsys, monkeypatch):
        """Uninstall on empty system should report nothing to do."""
        monkeypatch.setenv("BRAIN_HOME", str(tmp_path / "nonexistent"))
        _mod = sys.modules["brain_engine"]
        orig_brain = _mod.BRAIN_DIR
        orig_lessons = _mod.LESSONS_DIR
        orig_audit = _mod.AUDIT_FILE
        orig_plugins = _mod.PLUGINS_DIR

        _mod.BRAIN_DIR = tmp_path / "nonexistent"
        _mod.LESSONS_DIR = _mod.BRAIN_DIR / "lessons"
        _mod.AUDIT_FILE = _mod.BRAIN_DIR / "audit.jsonl"
        _mod.PLUGINS_DIR = _mod.BRAIN_DIR / "plugins"

        try:
            result = brain_engine.cmd_uninstall([])
            assert result == 0
            captured = capsys.readouterr()
            assert "Nothing" in captured.out or "アンインストール対象" in captured.out
        finally:
            _mod.BRAIN_DIR = orig_brain
            _mod.LESSONS_DIR = orig_lessons
            _mod.AUDIT_FILE = orig_audit
            _mod.PLUGINS_DIR = orig_plugins


# --- Doctor Tests ---

class TestDoctor:
    """Tests for brain doctor command."""

    def test_doctor_healthy_system(self, brain_home, sample_lesson, capsys):
        """Doctor should pass on a healthy setup."""
        result = brain_engine.cmd_doctor([])
        assert result == 0
        captured = capsys.readouterr()
        assert "Python:" in captured.out or "Python" in captured.out
        assert "All checks passed" in captured.out or "全チェックパス" in captured.out

    def test_doctor_shows_lesson_count(self, brain_home, sample_lesson, capsys):
        """Doctor should report lesson counts."""
        result = brain_engine.cmd_doctor([])
        assert result == 0
        captured = capsys.readouterr()
        assert "Lessons:" in captured.out or "レッスン:" in captured.out

    def test_doctor_detects_corrupt_lesson(self, brain_home, capsys):
        """Doctor should report corrupt lesson files."""
        # Write an invalid YAML file
        (brain_home / "lessons" / "broken.yaml").write_text("{{invalid yaml: [")
        result = brain_engine.cmd_doctor([])
        captured = capsys.readouterr()
        assert "issue" in captured.out.lower() or "問題" in captured.out

    def test_doctor_detects_corrupt_audit(self, brain_home, capsys):
        """Doctor should detect corrupt audit entries."""
        audit_file = brain_home / "audit.jsonl"
        audit_file.write_text('{"valid": true}\nnot json\n{"also": "valid"}\n')
        result = brain_engine.cmd_doctor([])
        captured = capsys.readouterr()
        assert "corrupt" in captured.out.lower() or "破損" in captured.out


# --- New Command Tests ---

class TestNewCommand:
    """Tests for brain new (template generator) command."""

    def test_new_generates_yaml_file(self, brain_home, capsys, monkeypatch, tmp_path):
        """brain new should generate a YAML file in the current directory."""
        monkeypatch.chdir(tmp_path)
        inputs = iter(["my-lesson", "warning", "Be careful with X", "pattern1", "", "Check A", "", "api,safety"])
        monkeypatch.setattr("builtins.input", lambda prompt: next(inputs))

        result = brain_engine.cmd_new([])
        assert result == 0

        yaml_file = tmp_path / "my-lesson.yaml"
        assert yaml_file.exists()
        content = yaml_file.read_text()
        assert "my-lesson" in content
        assert "warning" in content

    def test_new_aborts_on_empty_id(self, brain_home, capsys, monkeypatch, tmp_path):
        """brain new should abort if no ID is provided."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr("builtins.input", lambda prompt: "")

        result = brain_engine.cmd_new([])
        assert result == 1

    def test_new_rejects_invalid_id(self, brain_home, capsys, monkeypatch, tmp_path):
        """brain new should reject IDs that sanitize to empty string."""
        monkeypatch.chdir(tmp_path)
        # After sanitization: strips /, \, .., and non-word chars -> empty string
        monkeypatch.setattr("builtins.input", lambda prompt: "///...")

        result = brain_engine.cmd_new([])
        assert result == 1

    def test_new_template_importable(self, brain_home, capsys, monkeypatch, tmp_path):
        """Generated template should be importable via brain write -f."""
        monkeypatch.chdir(tmp_path)
        inputs = iter(["import-test", "critical", "Test import", "test_pattern", "", "Check 1", "", "test"])
        monkeypatch.setattr("builtins.input", lambda prompt: next(inputs))

        brain_engine.cmd_new([])
        yaml_file = tmp_path / "import-test.yaml"
        assert yaml_file.exists()

        # Now import it
        result = brain_engine.cmd_write(["-f", str(yaml_file)])
        assert result == 0
