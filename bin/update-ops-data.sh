#!/usr/bin/env bash
# Generate ops-data.json from live system metrics for the Ops Constellation dashboard.
# This decouples data collection from visualization so either can evolve independently.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
OUT="$PROJECT_DIR/docs/evidence/live/ops-data.json"
LOOP_LOG="${HOME}/.cache/cc-codex-consult/loop.log"
DECISION_LOG="${HOME}/ops/decision-log.md"

now=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

# --- Consult Loop Metrics ---
relay_total=0
relay_ok=0
relay_fail=0
relay_events="[]"

if [[ -f "$LOOP_LOG" ]]; then
  relay_total=$(grep -c "relay turn completed" "$LOOP_LOG" || true)
  relay_ok=$(grep -c "send ok" "$LOOP_LOG" || true)
  relay_fail=$(grep -c "send failed" "$LOOP_LOG" || true)

  # Build timeline of relay events (last 30)
  relay_events=$(grep -E "(relay turn completed|send ok|send failed|consult loop started)" "$LOOP_LOG" \
    | tail -30 \
    | python3 -c '
import sys, json, re
events = []
for line in sys.stdin:
    m = re.match(r"\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\] (.+)", line.strip())
    if m:
        ts, msg = m.groups()
        status = "ok" if "completed" in msg or "ok" in msg else ("fail" if "failed" in msg else "start")
        events.append({"ts": ts, "msg": msg.strip(), "status": status})
print(json.dumps(events))
')
fi

# --- ERR_CODE Metrics ---
err_open=0
err_list="[]"
if command -v err-tracker &>/dev/null; then
  err_output=$(err-tracker list 2>/dev/null || echo "(none)")
  if [[ "$err_output" != "(none)" && -n "$err_output" ]]; then
    err_open=$(echo "$err_output" | grep -c "^ERR_" || true)
    err_list=$(echo "$err_output" | python3 -c '
import sys, json
errors = []
for line in sys.stdin:
    line = line.strip()
    if line.startswith("ERR_"):
        errors.append(line)
print(json.dumps(errors))
')
  fi
fi

# --- Release Metrics ---
# TestPyPI publication data (hardcoded for MVP, script-updateable later)
release_version="0.1.0"
release_url="https://test.pypi.org/project/shared-brain/0.1.0/"
release_verified=true

# --- Decision Log ---
decisions="[]"
if [[ -f "$DECISION_LOG" ]]; then
  decisions=$(grep "^|" "$DECISION_LOG" | grep -v "^| #\|^|---" | tail -5 | python3 -c '
import sys, json, re
decisions = []
for line in sys.stdin:
    parts = [p.strip() for p in line.strip("|").split("|")]
    if len(parts) >= 5:
        decisions.append({
            "id": parts[0].strip(),
            "timestamp": parts[1].strip(),
            "decision": parts[2].strip(),
            "proposed_by": parts[3].strip(),
            "dod": parts[4].strip()
        })
print(json.dumps(decisions))
')
fi

# --- Infrastructure Health ---
consult_status="unknown"
if command -v cc-codex-consult-loop &>/dev/null; then
  if cc-codex-consult-loop --status 2>/dev/null | grep -q "running"; then
    consult_status="running"
  else
    consult_status="stopped"
  fi
fi

tmux_alive=false
if tmux has-session -t cc-codex 2>/dev/null; then
  tmux_alive=true
fi

# --- Phase Status ---
phase1_done=true
phase2_brainstorm=true
phase2_task_done=true
phase2_creative=false  # This dashboard IS the creative output

# --- Assemble JSON ---
cat > "$OUT" << ENDJSON
{
  "generated_at": "$now",
  "consult_loop": {
    "status": "$consult_status",
    "relay_total": $relay_total,
    "relay_ok": $relay_ok,
    "relay_fail": $relay_fail,
    "success_rate": $(python3 -c "print(round($relay_ok / max($relay_ok + $relay_fail, 1) * 100, 1))"),
    "timeline": $relay_events
  },
  "err_tracker": {
    "open_count": $err_open,
    "errors": $err_list
  },
  "release": {
    "version": "$release_version",
    "registry": "TestPyPI",
    "url": "$release_url",
    "install_verified": $release_verified
  },
  "decisions": $decisions,
  "infrastructure": {
    "consult_loop": "$consult_status",
    "tmux_session": $tmux_alive
  },
  "phase": {
    "p1_stable_comms": $phase1_done,
    "p2_brainstorm": $phase2_brainstorm,
    "p2_task_executed": $phase2_task_done,
    "p2_creative_output": $phase2_creative
  }
}
ENDJSON

echo "Updated: $OUT"
