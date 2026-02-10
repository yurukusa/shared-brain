#!/usr/bin/env python3
"""
Shared Brain Benchmark — Performance testing for guard operations.

Creates temporary lessons, runs guard checks, and reports timing stats.
Usage:
    python3 tests/benchmark.py
    brain benchmark  (if registered as a command)
"""

import sys
import os
import time
import tempfile
import shutil
import statistics
import json
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import brain_engine


def generate_lessons(n: int, lessons_dir: Path) -> list:
    """Generate n synthetic lessons with varied trigger patterns."""
    lessons = []
    categories = [
        ("api", ["PUT", "DELETE", "POST.*prod", "curl.*-X"]),
        ("git", ["git push.*force", "git reset.*hard", "git clean"]),
        ("file", ["rm -rf", "chmod 777", "dd if=", "mkfs"]),
        ("db", ["DROP TABLE", "TRUNCATE", "DELETE FROM.*WHERE 1", "ALTER TABLE.*DROP"]),
        ("deploy", ["deploy.*prod", "kubectl delete", "terraform destroy"]),
    ]

    for i in range(n):
        cat_name, base_patterns = categories[i % len(categories)]
        # Vary patterns to avoid trivial caching
        pattern_suffix = f"_{i}" if i >= len(categories) else ""
        patterns = [f"{p}{pattern_suffix}" for p in base_patterns[:2]]

        lesson = {
            "id": f"bench-{cat_name}-{i:04d}",
            "severity": ["critical", "warning", "info"][i % 3],
            "created": "2026-02-11",
            "violated_count": i % 5,
            "trigger_patterns": patterns,
            "lesson": f"Benchmark lesson {i} for {cat_name} category.\nDo not do this in production.",
            "checklist": [f"Check step {j}" for j in range(1, 4)],
            "tags": [cat_name, "benchmark"],
        }
        lessons.append(lesson)

        # Write to disk
        brain_engine.dump_yaml(lesson, lessons_dir / f"bench-{i:04d}.yaml")

    return lessons


def run_guard_benchmark(commands: list, iterations: int) -> dict:
    """Run guard checks and collect timing data."""
    times = []
    matches_found = 0

    for i in range(iterations):
        cmd = commands[i % len(commands)]
        start = time.perf_counter()
        # Use guard internals directly to avoid I/O overhead from print
        lessons = brain_engine.load_all_lessons()
        matched = []
        for lesson in lessons:
            patterns = lesson.get("trigger_patterns", [])
            for pattern in patterns:
                import re
                try:
                    if re.search(pattern, cmd, re.IGNORECASE):
                        matched.append(lesson)
                        break
                except re.error:
                    if pattern.lower() in cmd.lower():
                        matched.append(lesson)
                        break
        elapsed = time.perf_counter() - start
        times.append(elapsed * 1000)  # Convert to ms
        if matched:
            matches_found += 1

    return {
        "iterations": iterations,
        "matches_found": matches_found,
        "times_ms": times,
        "mean_ms": statistics.mean(times),
        "median_ms": statistics.median(times),
        "p95_ms": sorted(times)[int(len(times) * 0.95)],
        "p99_ms": sorted(times)[int(len(times) * 0.99)],
        "min_ms": min(times),
        "max_ms": max(times),
        "total_s": sum(times) / 1000,
    }


def run_lesson_load_benchmark(iterations: int) -> dict:
    """Benchmark lesson loading from disk."""
    times = []
    for _ in range(iterations):
        start = time.perf_counter()
        lessons = brain_engine.load_all_lessons()
        elapsed = time.perf_counter() - start
        times.append(elapsed * 1000)

    return {
        "iterations": iterations,
        "lessons_loaded": len(lessons),
        "mean_ms": statistics.mean(times),
        "median_ms": statistics.median(times),
        "min_ms": min(times),
        "max_ms": max(times),
    }


def main():
    print("🧠 Shared Brain Benchmark")
    print("=" * 60)

    # Setup: temp directory for benchmark lessons
    bench_dir = Path(tempfile.mkdtemp(prefix="brain-bench-"))
    original_lessons_dir = brain_engine.LESSONS_DIR
    original_builtin = brain_engine.BUILTIN_LESSONS

    try:
        # Override lesson directories
        brain_engine.LESSONS_DIR = bench_dir
        brain_engine.LESSONS_DIR.mkdir(parents=True, exist_ok=True)

        # Phase 1: Generate lessons
        print(f"\n📝 Phase 1: Generating 100 benchmark lessons...")
        start = time.perf_counter()
        lessons = generate_lessons(100, bench_dir)
        gen_time = (time.perf_counter() - start) * 1000
        print(f"   Generated 100 lessons in {gen_time:.1f}ms")

        # Phase 2: Lesson loading benchmark
        print(f"\n📂 Phase 2: Lesson loading (50 iterations)...")
        load_results = run_lesson_load_benchmark(50)
        print(f"   {load_results['lessons_loaded']} lessons loaded per iteration")
        print(f"   Mean: {load_results['mean_ms']:.2f}ms | Median: {load_results['median_ms']:.2f}ms")
        print(f"   Min: {load_results['min_ms']:.2f}ms | Max: {load_results['max_ms']:.2f}ms")

        # Phase 3: Guard check benchmark
        test_commands = [
            "curl -X PUT https://api.example.com/articles/123",
            "git push --force origin main",
            "rm -rf /tmp/old-data",
            "DROP TABLE users;",
            "kubectl delete deployment prod-app",
            "echo hello world",  # Should not match
            "ls -la",            # Should not match
            "python3 app.py",    # Should not match
            "npm install react", # Should not match
            "cat README.md",     # Should not match
        ]

        print(f"\n⚡ Phase 3: Guard checks (1000 iterations, 100 lessons)...")
        guard_results = run_guard_benchmark(test_commands, 1000)
        print(f"   Iterations: {guard_results['iterations']}")
        print(f"   Matches:    {guard_results['matches_found']} / {guard_results['iterations']}")
        print(f"   Mean:       {guard_results['mean_ms']:.2f}ms")
        print(f"   Median:     {guard_results['median_ms']:.2f}ms")
        print(f"   P95:        {guard_results['p95_ms']:.2f}ms")
        print(f"   P99:        {guard_results['p99_ms']:.2f}ms")
        print(f"   Min:        {guard_results['min_ms']:.2f}ms")
        print(f"   Max:        {guard_results['max_ms']:.2f}ms")
        print(f"   Total:      {guard_results['total_s']:.2f}s")

        # Phase 4: Throughput
        ops_per_sec = guard_results['iterations'] / guard_results['total_s']
        print(f"\n📊 Throughput: {ops_per_sec:.0f} guard checks/second")

        # Summary
        print(f"\n{'=' * 60}")
        print(f"✅ Benchmark Complete")
        print(f"   100 lessons, 1000 guard checks")
        print(f"   Average guard latency: {guard_results['mean_ms']:.2f}ms")
        print(f"   P99 guard latency:     {guard_results['p99_ms']:.2f}ms")
        print(f"   Throughput:            {ops_per_sec:.0f} ops/sec")

        # Verdict
        if guard_results['p99_ms'] < 50:
            print(f"   Verdict: ✅ FAST (P99 < 50ms)")
        elif guard_results['p99_ms'] < 200:
            print(f"   Verdict: 🟡 ACCEPTABLE (P99 < 200ms)")
        else:
            print(f"   Verdict: 🔴 SLOW (P99 >= 200ms)")

    finally:
        # Cleanup
        brain_engine.LESSONS_DIR = original_lessons_dir
        brain_engine.BUILTIN_LESSONS = original_builtin
        shutil.rmtree(bench_dir, ignore_errors=True)

    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
