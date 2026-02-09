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
