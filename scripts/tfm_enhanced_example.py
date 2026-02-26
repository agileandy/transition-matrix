#!/usr/bin/env python3
"""
Example: Using TFM with enhanced features

Demonstrates:
1. Success rate tracking
2. Expected behavior definitions
3. Baseline comparison
4. Error pattern clustering
5. Performance tracking
"""

import json
import random
from pathlib import Path
from tfm_decorator import (
    TransitionTracker,
    track_state,
    compare_to_baseline,
    cluster_errors,
)

# Define test cases with expected behavior
TEST_CASES = [
    {
        "id": 1,
        "input": "How should I name Python functions?",
        "expected_outcome": "SUCCESS",
        "description": "Valid query with good search terms",
    },
    {
        "id": 2,
        "input": "x",
        "expected_outcome": "FAIL",
        "expected_failure_at": "SearchMemory",
        "expected_error": "Query too short",
        "description": "Invalid input - too short",
    },
    {
        "id": 3,
        "input": "What's our AWS deployment process?",
        "expected_outcome": "SUCCESS",
        "description": "Valid query with technical terms",
    },
]


@track_state("SearchMemory")
def search_memory(query: str) -> list:
    """Extract search terms from query."""
    if len(query) < 3:
        raise ValueError("Query too short")
    return query.lower().split()[:3]


@track_state("RetrieveInsights")
def retrieve_insights(search_terms: list) -> dict:
    """Simulate ripgrep search."""
    if not search_terms:
        raise RuntimeError("No search terms provided")

    # Simulate occasional failures
    if random.random() < 0.15:
        raise RuntimeError("Memory file not found")

    return {"matches": random.randint(0, 5), "terms": search_terms}


def run_workflow(test_case: dict, tracker: TransitionTracker):
    """Run a single workflow."""
    tracker.set_state("START")

    try:
        search_terms = search_memory(test_case["input"])
        insights = retrieve_insights(search_terms)
        return "SUCCESS"
    except Exception as e:
        return f"FAILED: {e}"


def main():
    tracker = TransitionTracker.get_instance()
    baseline_file = Path("baseline.json")

    print("\n" + "=" * 70)
    print("TFM Enhanced Example")
    print("=" * 70 + "\n")

    # Run test cases
    print(f"Running {len(TEST_CASES) * 10} test cases...\n")
    for _ in range(10):
        for test_case in TEST_CASES:
            result = run_workflow(test_case, tracker)

    # 1. Success/Failure Rates
    print("=" * 70)
    print("SUCCESS/FAILURE RATES")
    print("=" * 70 + "\n")

    rates = tracker.get_transition_rates()
    for transition, stats in sorted(rates.items(), key=lambda x: -x[1]["failure_rate"]):
        rate = stats["failure_rate"]
        status = "🔥🔥🔥" if rate > 50 else "🔥🔥" if rate > 20 else "🔥" if rate > 5 else "✓"
        print(
            f"{status} {transition}: {stats['failures']}/{stats['total']} "
            f"({rate:.1f}%) | Avg: {stats['avg_duration_ms']:.1f}ms"
        )

    # 2. Error Pattern Clustering
    print("\n" + "=" * 70)
    print("ERROR PATTERN ANALYSIS")
    print("=" * 70 + "\n")

    error_patterns = cluster_errors(tracker.events)
    for error_msg, events in sorted(error_patterns.items(), key=lambda x: -len(x[1])):
        print(f"'{error_msg}': {len(events)} occurrences")
        transitions = set(f"{e.from_state} → {e.to_state}" for e in events)
        print(f"  Affects: {', '.join(list(transitions)[:3])}\n")

    # 3. Performance Bottlenecks
    print("=" * 70)
    print("PERFORMANCE BOTTLENECKS")
    print("=" * 70 + "\n")

    slow = tracker.get_slow_transitions(threshold_ms=50)
    if slow:
        for transition, avg_ms, count in slow:
            print(f"⏱️  {transition}: {avg_ms:.1f}ms avg ({count} samples)")
    else:
        print("✓ No slow transitions detected")

    # 4. Baseline Comparison
    print("\n" + "=" * 70)
    print("REGRESSION ANALYSIS")
    print("=" * 70 + "\n")

    if baseline_file.exists():
        with open(baseline_file) as f:
            baseline_rates = json.load(f)

        regressions = compare_to_baseline(rates, baseline_rates, threshold=0.2)

        if regressions:
            print("⚠️  REGRESSIONS DETECTED:\n")
            for reg in regressions:
                print(f"  {reg['transition']}")
                print(
                    f"    Baseline: {reg['baseline_rate']:.1f}% → "
                    f"Current: {reg['current_rate']:.1f}%"
                )
                print(f"    Delta: +{reg['delta']:.1f}% ({reg['percent_increase']:.0f}% increase)\n")
        else:
            print("✓ No regressions detected (within 20% of baseline)")
    else:
        print("No baseline found. Creating baseline...")
        with open(baseline_file, "w") as f:
            json.dump(rates, f, indent=2)
        print(f"✓ Baseline saved to {baseline_file}")

    # 5. Prioritized Recommendations
    print("\n" + "=" * 70)
    print("PRIORITIZED RECOMMENDATIONS")
    print("=" * 70 + "\n")

    # Sort by impact (failure_rate * total_attempts)
    priorities = []
    for transition, stats in rates.items():
        if stats["failures"] > 0:
            impact = stats["failure_rate"] * stats["total"]
            priorities.append((transition, stats, impact))

    priorities.sort(key=lambda x: -x[2])

    if priorities:
        for rank, (transition, stats, impact) in enumerate(priorities[:3], 1):
            print(f"{rank}. Fix: {transition}")
            print(
                f"   Impact: {stats['failures']} failures "
                f"({stats['failure_rate']:.1f}% of {stats['total']} attempts)"
            )
            print(f"   Fixing this addresses {stats['failures']} failures\n")
    else:
        print("✓ No failures detected!")

    # 6. Sankey Diagram Visualization
    print("\n" + "=" * 70)
    print("SANKEY DIAGRAM VISUALIZATION")
    print("=" * 70 + "\n")

    print(tracker.render_sankey())
    print("\n💡 Copy the above Mermaid diagram to GitHub/markdown to visualize flow")


if __name__ == "__main__":
    main()
